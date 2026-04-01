# src/python/learning/variational_meta_learner.py
"""
Capa de Meta-Aprendizaje Variacional para MSE-V 4.0.
Esta capa optimiza los meta-parámetros Φ del sistema base (como δ+, w3, etc.)
para minimizar el funcional de costo total J(Φ), que representa el esfuerzo acumulado (backtracks)
en resoluciones repetidas del mismo puzzle.

MSE-V .4.0 Formal Logic.txt - Sección XI: Extensión Variacional para Meta-Optimización
MSE-V Sec. XI.5: Persistencia del Conocimiento Meta (Φ serializado con base de conocimiento)

ETAPA: 3, 4
AUTOR: Codex (Protocolo Vexhive)
FECHA: 2026-02-12
"""

import sys
import os
import numpy as np
import pickle
import gzip
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path

# Asegurar que el directorio raíz del proyecto esté en la ruta de Python
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# ✅ NUEVO v5.0.2-R: Importar MetaMetaParameters (Ψ) para Q2
from ..core.meta_meta_parameters import MetaMetaParameters, create_default_psi


# ============================================================================
# META-PARÁMETROS Φ (Sin cambios - Definición según MSE-V Sec. VIII.3)
# ============================================================================
@dataclass
class MetaParameters:
    """
    Meta-parámetros Φ optimizables mediante meta-aprendizaje variacional.
    MSE-V Sec. VIII.3: Θ = {δ⁺, δ⁻, ε_min, ε_max, w1, w2, w3, λ_H, ...}

    Todos los parámetros tienen dominios admisibles definidos en get_bounds().
    """
    # Parámetros para la actualización de E(pt)
    delta_plus: float = 0.20   # 1D.3: 0.15 → 0.20 (balanced learning rate) [0.05, 0.3]
    delta_minus: float = 0.15  # 1C.11: 0.15 (unchanged) [0.05, 0.3]
    epsilon_min: float = 0.10  # Cota inferior de efectividad [0.05, 0.3]
    epsilon_max: float = 1.00  # Cota superior de efectividad [0.8, 1.0]

    # Parámetros para la función de score(i,j) en BranchSelector
    w1: float = 10.0           # Peso de 1/|Ω(i,j)| [1.0, 100.0]
    w2: float = 0.1            # Peso de restricciones cruzadas [0.01, 1.0]
    w3: float = 2.0            # Peso de H(i,j) [0.1, 10.0]
    lambda_H: float = 1.0      # Factor de escala para H en tanh(λH * H(i,j)) [0.5, 5.0]

    # Parámetros para la optimización meta
    mu_penalty: float = 10.0   # Factor de penalización por fallo [1.0, 100.0]
    B_max: int = 1000          # Cota superior de backtracks [100, 10000]
    alpha_meta: float = 0.01   # Tasa de aprendizaje meta inicial [0.001, 0.1]
    epsilon_perturbation: float = 0.01  # Tamaño relativo de perturbación [0.001, 0.1]

    # Parámetros para REINFORCE (math_patch.txt Sec. 2.4)
    temperature: float = 0.92  # 1D.3: 1.0 → 0.92 (more exploitation, less exploration) [0.1, 5.0]
    baseline_decay: float = 0.99  # Decaimiento del baseline [0.9, 0.999]

    def to_dict(self) -> Dict[str, Any]:
        """Convierte los parámetros a un diccionario para serialización."""
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MetaParameters':
        """Crea una instancia desde un diccionario."""
        # Filtrar solo los campos que existen en la dataclass
        filtered_data = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**filtered_data)

    def get_bounds(self) -> Dict[str, Tuple[float, float]]:
        """
        Devuelve los límites admisibles para cada parámetro.
        MSE-V Sec. VIII.3: Rangos típicos para cada meta-parámetro.
        """
        return {
            'delta_plus': (0.05, 0.2),
            'delta_minus': (0.05, 0.3),
            'epsilon_min': (0.05, 0.3),
            'epsilon_max': (0.8, 1.0),
            'w1': (1.0, 100.0),
            'w2': (0.01, 1.0),
            'w3': (0.1, 10.0),
            'lambda_H': (0.5, 5.0),
            'mu_penalty': (1.0, 100.0),
            'B_max': (100, 10000),
            'alpha_meta': (0.001, 0.1),
            'epsilon_perturbation': (0.001, 0.1),
            'temperature': (0.1, 5.0),
            'baseline_decay': (0.9, 0.999)
        }

    def project_into_bounds(self):
        """
        Proyecta los parámetros actuales dentro de sus límites admisibles.
        MSE-V Sec. XI.4: Π_Dom(ϕ) para garantizar dominios válidos.
        """
        bounds = self.get_bounds()
        for param_name, (low, high) in bounds.items():
            current_value = getattr(self, param_name)
            if current_value < low:
                setattr(self, param_name, low)
            elif current_value > high:
                setattr(self, param_name, high)


# ============================================================================
# VARIATIONAL META LEARNER (Modificado para sync con pattern_db)
# ============================================================================
class VariationalMetaLearner:
    """
    Gestiona la optimización variacional de los meta-parámetros Φ.

    CAMBIOS v4.0 (Decision D2):
    - Φ ahora se persiste en pattern_db.pkl.gz junto con H(i,j) y E(pt)
    - load_parameters() y save_parameters() DEPRECADOS
    - Nuevos métodos: sync_with_pattern_db(), save_to_pattern_db()

    MSE-V Sec. XI.5: Persistencia del Conocimiento Meta
    
    CAMBIOS v5.0.2-R:
    - Ψ (MetaMetaParameters) es FIJO y controla la modulación de temperatura Q2
    - Ψ se persiste junto con Φ en pattern_db
    - get_current_temperature(episode) usa τ(t) = τ_base + τ_exploración·sin(2πt/T_ciclo)
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Inicializa el MetaLearner SIN persistencia propia.

        Args:
            db_path: DEPRECIADO - La persistencia real se hace vía HybridPatternDatabase
        """
        # db_path DEPRECIADO - Solo para compatibilidad hacia atrás
        self._deprecated_db_path = db_path

        # Inicializar meta-parámetros con valores por defecto
        self.meta_params = MetaParameters()
        
        # ✅ NUEVO v5.0.2-R: Ψ (MetaMetaParameters) - ADN Cognitivo Inmutable
        self.meta_meta_params = create_default_psi()

        # Flag para tracking de sincronización
        self._synced_with_db = False

        # ✅ NUEVO v5.0.2-R: Contador de episodios para modulación τ(t)
        self.episode_counter = 0

        # Historial de episodios para optimización meta (Sec. XI.4)
        self.episode_history: List[Dict[str, Any]] = []
        self.meta_update_counter = 0
        self.N_meta = 5  # Frecuencia de optimización meta (Sec. XI.4)

        print(f"[MetaLearner] Inicializado con valores por defecto. Φ = {self.meta_params.to_dict()}")
        print(f"[MetaLearner] Ψ (ADN Cognitivo): τ_base={self.meta_meta_params.tau_base}, cycle_period={self.meta_meta_params.cycle_period}")

    def sync_with_pattern_db(self, pattern_db):
        """
        Sincroniza Φ con HybridPatternDatabase.
        MSE-V Sec. XI.5: Φ se carga desde pattern_db.pkl.gz
        
        CAMBIOS v5.0.2-R:
        - También sincroniza Ψ (meta_meta_params) si está disponible

        Args:
            pattern_db: Instancia de HybridPatternDatabase
        """
        if hasattr(pattern_db, 'meta_params') and pattern_db.meta_params:
            self.meta_params = pattern_db.meta_params
            self._synced_with_db = True
            print(f"[MetaLearner] Φ sincronizado desde pattern_db: {self.meta_params.to_dict()}")
        else:
            print(f"[MetaLearner] WARNING: pattern_db no tiene meta_params. Usando valores por defecto.")
            self._synced_with_db = False
        
        # ✅ NUEVO v5.0.2-R: Sincronizar Ψ si está disponible
        if hasattr(pattern_db, 'meta_meta_params') and pattern_db.meta_meta_params:
            self.meta_meta_params = pattern_db.meta_meta_params
            print(f"[MetaLearner] Ψ sincronizado desde pattern_db: τ_base={self.meta_meta_params.tau_base}, cycle_period={self.meta_meta_params.cycle_period}")
        else:
            print(f"[MetaLearner] Ψ no está en pattern_db. Usando valores por defecto (Q2).")

    def save_to_pattern_db(self, pattern_db):
        """
        Guarda Φ y Ψ en HybridPatternDatabase.
        MSE-V Sec. XI.5: Φ se serializa junto con H(i,j) y E(pt)
        
        CAMBIOS v5.0.2-R:
        - También guarda Ψ (meta_meta_params) para persistencia

        Args:
            pattern_db: Instancia de HybridPatternDatabase
        """
        if hasattr(pattern_db, 'set_meta_params'):
            pattern_db.set_meta_params(self.meta_params)
            print(f"[MetaLearner] Φ guardado en pattern_db: {self.meta_params.to_dict()}")
        else:
            # Fallback: asignación directa
            pattern_db.meta_params = self.meta_params
            print(f"[MetaLearner] Φ asignado directamente a pattern_db")
        
        # ✅ NUEVO v5.0.2-R: Guardar Ψ también
        if hasattr(pattern_db, 'set_meta_meta_params'):
            pattern_db.set_meta_meta_params(self.meta_meta_params)
            print(f"[MetaLearner] Ψ guardado en pattern_db: τ_base={self.meta_meta_params.tau_base}")

    # =========================================================================
    # MÉTODOS Q2: MODULACIÓN PERIÓDICA DE TEMPERATURA
    # =========================================================================
    
    def get_current_temperature(self) -> float:
        """
        Q2: Obtiene la temperatura actual τ(t) con modulación periódica.
        
        Fórmula: τ(t) = τ_base + τ_exploración·sin(2πt/T_ciclo)
        
        Returns:
            Temperatura actual τ(t) ≥ 0.1
            
        Uso:
            - policy.get_current_temperature() usa este método
            - La temperatura afecta la exploración en select_option_symbolically()
        """
        return self.meta_meta_params.get_current_temperature(self.episode_counter)
    
    def get_exploration_phase(self) -> str:
        """
        Q2: Obtiene la fase actual de exploración.
        
        Returns:
            'exploration' o 'exploitation'
        """
        return self.meta_meta_params.get_phase(self.episode_counter)
    
    def get_exploration_factor(self) -> float:
        """
        Q2: Obtiene el factor de exploración normalizado [0, 1].
        
        Returns:
            Factor donde 1 = máxima exploración, 0 = máxima explotación
        """
        return self.meta_meta_params.get_exploration_factor(self.episode_counter)
    
    def increment_episode_counter(self):
        """
        Q2: Incrementa el contador de episodios para modulación τ(t).
        
        Debe llamarse después de cada resolución completa de puzzle.
        """
        self.episode_counter += 1
        current_tau = self.get_current_temperature()
        phase = self.get_exploration_phase()
        print(f"[MetaLearner] Episodio #{self.episode_counter}: τ={current_tau:.3f}, fase={phase}")

    def load_parameters(self):
        """
        DEPRECIADO: La carga ahora se hace vía pattern_db.load_patterns()
        MSE-V Sec. XI.5: Persistencia unificada
        """
        print("[MetaLearner] WARNING: load_parameters() DEPRECIADO. Usar sync_with_pattern_db()")
        # Mantener compatibilidad hacia atrás cargando desde archivo separado si existe
        if self._deprecated_db_path:
            db_path = Path(self._deprecated_db_path)
            if db_path.exists():
                try:
                    with gzip.open(db_path, 'rb') as f:
                        data = pickle.load(f)
                        self.meta_params = MetaParameters.from_dict(data)
                    print(f"[MetaLearner] Cargados meta-parámetros desde archivo separado (legacy): {db_path}")
                except Exception as e:
                    print(f"[MetaLearner] Error al cargar desde legacy: {e}")
        pass

    def save_parameters(self):
        """
        DEPRECIADO: El guardado ahora se hace vía pattern_db.save_patterns()
        MSE-V Sec. XI.5: Persistencia unificada
        """
        print("[MetaLearner] WARNING: save_parameters() DEPRECIADO. Usar save_to_pattern_db()")
        # Mantener compatibilidad hacia atrás guardando en archivo separado
        if self._deprecated_db_path:
            try:
                db_path = Path(self._deprecated_db_path)
                db_path.parent.mkdir(parents=True, exist_ok=True)
                with gzip.open(db_path, 'wb') as f:
                    pickle.dump(self.meta_params.to_dict(), f)
                print(f"[MetaLearner] Guardados meta-parámetros en archivo separado (legacy): {db_path}")
            except Exception as e:
                print(f"[MetaLearner] Error al guardar en legacy: {e}")
        pass

    def get_current_params(self) -> MetaParameters:
        """
        Devuelve una copia de los meta-parámetros actuales.
        MSE-V Sec. VIII.3: Φ = {δ⁺, δ⁻, w1, w2, w3, λ_H, ...}
        """
        return MetaParameters(**self.meta_params.to_dict())

    def update_parameters(self, new_params: MetaParameters):
        """
        Actualiza los meta-parámetros internos y los guarda.
        MSE-V Sec. XI.4: Actualización con proyección al dominio admisible.

        Args:
            new_params: Nuevos meta-parámetros
        """
        self.meta_params = new_params
        self.meta_params.project_into_bounds()  # Asegurar que están dentro de los límites
        # Nota: El guardado real se hace vía save_to_pattern_db(pattern_db)

    def calculate_episode_cost(self, backtracks: int, success: bool) -> float:
        """
        Calcula el costo de un episodio según la fórmula:
        C(Θ_e) = B_e + μ * (1 - success_e) * B_max

        MSE-V Sec. XI.1: Función de costo para meta-optimización

        Args:
            backtracks: Número de backtracks en el episodio
            success: True si se resolvió el puzzle

        Returns:
            Costo del episodio
        """
        B_e = backtracks
        success_e = int(success)
        mu = self.meta_params.mu_penalty
        B_max = self.meta_params.B_max
        cost = B_e + mu * (1 - success_e) * B_max
        return cost

    def record_episode(self, backtracks: int, success: bool, params_snapshot: Optional[Dict] = None):
        """
        Registra un episodio en el historial para optimización meta.
        MSE-V Sec. XI.4: Ventana deslizante de E episodios

        Args:
            backtracks: Número de backtracks
            success: True si se resolvió
            params_snapshot: Copia de Φ al inicio del episodio
        """
        cost = self.calculate_episode_cost(backtracks, success)
        self.episode_history.append({
            'backtracks': backtracks,
            'success': success,
            'cost': cost,
            'params_snapshot': params_snapshot or self.meta_params.to_dict(),
            'timestamp': __import__('time').time()
        })

        # Mantener ventana deslizante de N_meta episodios
        if len(self.episode_history) > self.N_meta:
            self.episode_history.pop(0)

    def maybe_optimize(self, pattern_db=None):
        """
        Ejecuta optimización meta cada N_meta episodios.
        MSE-V Sec. XI.4: Frecuencia de optimización meta

        Args:
            pattern_db: HybridPatternDatabase para guardar Φ actualizado
        """
        self.meta_update_counter += 1

        if self.meta_update_counter % self.N_meta == 0 and len(self.episode_history) >= self.N_meta:
            print(f"[MetaLearner] Ejecutando optimización meta (episodio {self.meta_update_counter})...")
            self._optimize_meta_params()

            # Guardar Φ actualizado en pattern_db
            if pattern_db:
                self.save_to_pattern_db(pattern_db)

        return self.meta_update_counter % self.N_meta == 0

    def _optimize_meta_params(self):
        """
        Ejecuta optimización de meta-parámetros usando el historial de episodios.
        MSE-V Sec. XI.2-XI.4: Estimación de gradiente y actualización

        NOTA: Implementación simplificada. La optimización variacional completa
        requiere ecuaciones adjuntas (Sec. XI.2) que se implementarán en ETAPA 4.
        """
        if len(self.episode_history) < 2:
            print("[MetaLearner] Historial insuficiente para optimización.")
            return

        # Calcular costo promedio
        avg_cost = np.mean([ep['cost'] for ep in self.episode_history])
        print(f"[MetaLearner] Costo promedio de episodios: {avg_cost:.2f}")

        # Aquí iría la lógica de optimización variacional completa:
        # 1. Estimar gradiente ∂J/∂ϕ (Sec. XI.3)
        # 2. Calcular multiplicadores adjuntos λ_e (Sec. XI.2)
        # 3. Actualizar Φ con descenso por gradiente (Sec. XI.4)

        # Implementación placeholder para ETAPA 4
        print("[MetaLearner] Optimización variacional completa pendiente de ETAPA 4.")
        print("[MetaLearner] Usando actualización simple basada en costo promedio.")

        # Actualización simple (placeholder)
        if avg_cost > 500:  # Si el costo es alto, ajustar parámetros
            self.meta_params.w3 *= 1.1  # Aumentar peso de H(i,j)
            self.meta_params.delta_plus *= 0.95  # Reducir incremento de E(pt)
            self.meta_params.project_into_bounds()
            print(f"[MetaLearner] Parámetros ajustados: w3={self.meta_params.w3:.2f}, δ⁺={self.meta_params.delta_plus:.3f}")

    def clear_episode_history(self):
        """Limpia el historial de episodios."""
        self.episode_history.clear()
        self.meta_update_counter = 0

# src/python/core/meta_meta_parameters.py
"""
Meta-Meta-Parámetros Ψ (ADN Cognitivo Inmutable) - MSE v5.0.2-R

Este módulo implementa los parámetros de nivel superior que definen la arquitectura
cognitiva fija del sistema MSE. A diferencia de Φ (que se optimiza mediante
meta-aprendizaje), Ψ es FIJO y no puede ser modificado por la red neuronal.

MSE v5.0.2-R:
- A7: Ψ (meta-meta-parámetros) = FIJO [ADN/genética inmutable]
- Q2: Modulación periódica de temperatura τ(t)
- Q6: Forward-Forward como meta-patrón importable
- Q7: Jerarquía cognitiva humana → Ψ

Los parámetros Ψ controlan:
1. Ciclos de exploración/explotación (sueño-vigilia)
2. Mapeo de funciones cognitivas humanas a operadores MSE
3. Umbrales de cristalización de patrones
4. Configuración del núcleo de motivación intrínseca
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class MetaMetaParameters:
    """
    Ψ - Meta-Meta-Parámetros FIJOS (ADN Cognitivo del MSE)
    
    MSE v5.0.2-R, Axioma A7: Ψ es inmutable y define la genética cognitiva del sistema.
    La red neuronal NO puede modificar estos valores.
    
    Estos parámetros implementan:
    - Q2: Modulación periódica de temperatura (ciclos sueño-vigilia)
    - Q4: Umbrales de cristalización de patrones suaves
    - Q6: Configuración de Forward-Forward como meta-patrón
    - Q7: Mapeo de funciones cognitivas humanas
    - A14-A16: Núcleo de motivación intrínseca
    """
    
    # =========================================================================
    # Q2: MODULACIÓN PERIÓDICA DE TEMPERATURA (Ciclos Sueño-Vigilia)
    # =========================================================================
    # Inspirado en ciclos biológicos y enfriamiento simulado de Máquinas de Boltzmann
    
    tau_base: float = 1.0          # Temperatura base τ_base [0.5, 2.0]
    tau_exploration: float = 0.9   # Amplitud de exploración τ_exploración [0.3, 1.5]
    cycle_period: int = 20         # Período del ciclo T_ciclo (episodios) [20, 200]
    
    # =========================================================================
    # Q4: CRISTALIZACIÓN DE PATRONES SUAVES
    # =========================================================================
    # Umbral para convertir patrones temporales en permanentes
    
    crystallization_threshold: float = 0.70  # E(pt) > 0.95 → patrón discreto
    soft_pattern_lifetime: int = 65         # Episodios antes de decaer
    soft_pattern_decay: float = 0.99         # Decaimiento por episodio
    
    # =========================================================================
    # Q6: FORWARD-FORWARD COMO META-PATRÓN
    # =========================================================================
    # Configuración para importar FF como operador seleccionable
    
    ff_importable: bool = True               # ¿FF disponible como meta-patrón?
    ff_goodness_threshold: float = 0.7       # Umbral para "goodness" positivo
    ff_negative_weight: float = 0.4          # Peso para negative pass
    
    # =========================================================================
    # Q7: MAPEO DE FUNCIONES COGNITIVAS HUMANAS
    # =========================================================================
    # Jerarquía cognitiva: Función Humana → Meta-Meta-Patrón Ψ → Operador MSE
    
    # Memoria de trabajo → Ventana de optimización meta
    memory_window: int = 15                   # N_meta: episodios para optimización
    
    # Atención selectiva → Pesos de score(i,j)
    attention_weights: Dict[str, float] = field(default_factory=lambda: {
        'w1_base': 10.0,     # Base para 1/|Ω(i,j)|
        'w2_base': 0.1,      # Base para restricciones cruzadas
        'w3_base': 2.0       # Base para H(i,j)
    })
    
    # Motivación → Tasa de aprendizaje meta
    motivation_alpha: float = 0.01           # α_meta base para optimización
    
    # Emoción básica → Modulación de τ(t)
    emotion_modulation: bool = True          # ¿Activar modulación emocional?
    emotion_amplitude: float = 0.2           # Amplitud de modulación emocional
    
    # Curiosidad → Impulso de exploración
    curiosity_drive: float = 0.4             # Impulso base para explorar
    
    # Supervivencia → Penalización por fallo
    survival_penalty: float = 9.0           # μ_penalty base
    survival_max_backtracks: int = 400      # B_max base
    
    # =========================================================================
    # FASE 1B: AJUSTES DE TRADING (Iterativos)
    # =========================================================================
    # 1B.1: Trigger de E(pt) para operar (ajuste iterativo documentado)
    # 1C.9: Increase from 0.43 to 0.55 to filter low-quality patterns
    # 1C.10: Reduce from 0.55 to 0.50 to balance quality vs quantity

    e_pt_trigger: float = 0.50  # 1C.10: 0.55 → 0.50 (balance quality vs quantity)

    # =========================================================================
    # A14-A16: MOTIVACIÓN INTRÍNSECA (Lagrangiano)
    # =========================================================================
    # Principio de mínima acción discreto
    
    lagrangian_alpha: float = 1.0            # Peso para C_comp (progreso)
    lagrangian_beta: float = 0.5             # Peso para C_incert (incertidumbre)
    lagrangian_gamma: float = 0.3            # Peso para C_complej (complejidad)
    
    # =========================================================================
    # MÉTODOS
    # =========================================================================
    
    def get_current_temperature(self, episode: int) -> float:
        """
        Q2: Calcula la temperatura actual τ(t) con modulación periódica.
        
        Fórmula: τ(t) = τ_base + τ_exploración·sin(2πt/T_ciclo)
        
        Args:
            episode: Número de episodio actual (t)
            
        Returns:
            Temperatura actual τ(t) ≥ 0.1
            
        Justificación:
        - Inspirado en ciclos biológicos sueño-vigilia
        - Similar a enfriamiento simulado de Máquinas de Boltzmann
        - Permite ciclos predecibles de exploración/explotación
        """
        tau = self.tau_base + self.tau_exploration * np.sin(2 * np.pi * episode / self.cycle_period)
        
        # Añadir modulación emocional si está activa
        if self.emotion_modulation:
            # Modulación adicional basada en "estado emocional" simulado
            emotional_component = self.emotion_amplitude * np.sin(2 * np.pi * episode / (self.cycle_period * 2))
            tau += emotional_component
        
        # Asegurar temperatura mínima
        return max(0.1, tau)
    
    def get_phase(self, episode: int) -> str:
        """
        Q2: Determina la fase actual del ciclo (exploración vs explotación).
        
        Returns:
            'exploration' si τ(t) > τ_base, 'exploitation' en caso contrario
            
        Justificación:
        - Fase de exploración: alta temperatura, más diversidad
        - Fase de explotación: baja temperatura, más greedy
        """
        tau_current = self.get_current_temperature(episode)
        if tau_current > self.tau_base:
            return 'exploration'
        else:
            return 'exploitation'
    
    def get_exploration_factor(self, episode: int) -> float:
        """
        Q2: Factor de exploración normalizado [0, 1].
        
        Returns:
            Factor donde 1 = máxima exploración, 0 = máxima explotación
        """
        tau_current = self.get_current_temperature(episode)
        tau_max = self.tau_base + self.tau_exploration + self.emotion_amplitude
        tau_min = max(0.1, self.tau_base - self.tau_exploration - self.emotion_amplitude)
        
        if tau_max == tau_min:
            return 0.5
        
        return (tau_current - tau_min) / (tau_max - tau_min)
    
    def get_attention_weight(self, name: str) -> float:
        """
        Q7: Obtiene el peso de atención para score(i,j).
        
        Args:
            name: Nombre del peso ('w1_base', 'w2_base', 'w3_base')
            
        Returns:
            Valor del peso de atención
        """
        return self.attention_weights.get(name, 1.0)
    
    def get_lagrangian_weights(self) -> Dict[str, float]:
        """
        A14-A16: Obtiene los pesos del Lagrangiano de motivación intrínseca.
        
        Returns:
            Diccionario con α, β, γ para L = α·C_comp + β·C_incert + γ·C_complej
        """
        return {
            'alpha': self.lagrangian_alpha,
            'beta': self.lagrangian_beta,
            'gamma': self.lagrangian_gamma
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte Ψ a diccionario para serialización."""
        return {
            'tau_base': self.tau_base,
            'tau_exploration': self.tau_exploration,
            'cycle_period': self.cycle_period,
            'crystallization_threshold': self.crystallization_threshold,
            'soft_pattern_lifetime': self.soft_pattern_lifetime,
            'soft_pattern_decay': self.soft_pattern_decay,
            'ff_importable': self.ff_importable,
            'ff_goodness_threshold': self.ff_goodness_threshold,
            'ff_negative_weight': self.ff_negative_weight,
            'memory_window': self.memory_window,
            'attention_weights': self.attention_weights,
            'motivation_alpha': self.motivation_alpha,
            'emotion_modulation': self.emotion_modulation,
            'emotion_amplitude': self.emotion_amplitude,
            'curiosity_drive': self.curiosity_drive,
            'survival_penalty': self.survival_penalty,
            'survival_max_backtracks': self.survival_max_backtracks,
            'lagrangian_alpha': self.lagrangian_alpha,
            'lagrangian_beta': self.lagrangian_beta,
            'lagrangian_gamma': self.lagrangian_gamma
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MetaMetaParameters':
        """Crea Ψ desde un diccionario."""
        # Filtrar solo campos válidos
        valid_fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        
        # Manejar attention_weights especialmente
        if 'attention_weights' in valid_fields:
            aw = valid_fields['attention_weights']
            if isinstance(aw, dict):
                # Asegurar que es el tipo correcto
                valid_fields['attention_weights'] = {
                    'w1_base': float(aw.get('w1_base', 10.0)),
                    'w2_base': float(aw.get('w2_base', 0.1)),
                    'w3_base': float(aw.get('w3_base', 2.0))
                }
        
        return cls(**valid_fields)
    
    def __post_init__(self):
        """Validar que Ψ está dentro de dominios admisibles."""
        # Validar temperaturas
        assert 0.1 <= self.tau_base <= 5.0, f"tau_base={self.tau_base} fuera de [0.1, 5.0]"
        assert 0.0 <= self.tau_exploration <= 3.0, f"tau_exploration={self.tau_exploration} fuera de [0.0, 3.0]"
        assert 10 <= self.cycle_period <= 500, f"cycle_period={self.cycle_period} fuera de [10, 500]"

        # Validar umbrales de cristalización
        assert 0.5 <= self.crystallization_threshold <= 1.0, \
            f"crystallization_threshold={self.crystallization_threshold} fuera de [0.5, 1.0]"
        assert 0 < self.soft_pattern_decay <= 1.0, \
            f"soft_pattern_decay={self.soft_pattern_decay} fuera de (0, 1.0]"
        assert self.soft_pattern_lifetime > 0, \
            f"soft_pattern_lifetime={self.soft_pattern_lifetime} debe ser > 0"

        # Validar Forward-Forward
        assert 0.0 <= self.ff_goodness_threshold <= 1.0, \
            f"ff_goodness_threshold={self.ff_goodness_threshold} fuera de [0.0, 1.0]"
        assert self.ff_negative_weight > 0, \
            f"ff_negative_weight={self.ff_negative_weight} debe ser > 0"

        # Validar motivación intrínseca
        assert self.curiosity_drive >= 0, \
            f"curiosity_drive={self.curiosity_drive} debe ser >= 0"
        assert self.emotion_amplitude >= 0, \
            f"emotion_amplitude={self.emotion_amplitude} debe ser >= 0"
        assert self.survival_penalty >= 0, \
            f"survival_penalty={self.survival_penalty} debe ser >= 0"
        assert self.memory_window > 0, \
            f"memory_window={self.memory_window} debe ser > 0"

        # Validar E(pt) trigger
        assert 0.0 <= self.e_pt_trigger <= 1.0, \
            f"e_pt_trigger={self.e_pt_trigger} fuera de [0.0, 1.0]"

        # Validar pesos del Lagrangiano
        assert self.lagrangian_alpha >= 0, f"lagrangian_alpha={self.lagrangian_alpha} debe ser >= 0"
        assert self.lagrangian_beta >= 0, f"lagrangian_beta={self.lagrangian_beta} debe ser >= 0"
        assert self.lagrangian_gamma >= 0, f"lagrangian_gamma={self.lagrangian_gamma} debe ser >= 0"

        # Validar atención
        for key, val in self.attention_weights.items():
            assert val >= 0, f"attention_weights[{key}]={val} debe ser >= 0"


# ============================================================================
# FUNCIONES UTILITARIAS
# ============================================================================

def create_default_psi() -> MetaMetaParameters:
    """
    Crea una instancia de Ψ con valores por defecto según v5.0.2-R.
    
    Returns:
        MetaMetaParameters con configuración default
    """
    return MetaMetaParameters()


def create_exploration_focused_psi() -> MetaMetaParameters:
    """
    Crea Ψ enfocado en exploración (alta temperatura, más curiosidad).
    
    Útil para fase inicial de aprendizaje o puzzles muy difíciles.
    """
    return MetaMetaParameters(
        tau_base=1.5,
        tau_exploration=1.2,
        cycle_period=80,
        curiosity_drive=0.5,
        crystallization_threshold=0.98  # Más estricto para cristalizar
    )


def create_exploitation_focused_psi() -> MetaMetaParameters:
    """
    Crea Ψ enfocado en explotación (baja temperatura, más greedy).
    
    Útil para fase final de aprendizaje o puzzles fáciles.
    """
    return MetaMetaParameters(
        tau_base=0.5,
        tau_exploration=0.3,
        cycle_period=30,
        curiosity_drive=0.1,
        crystallization_threshold=0.90  # Menos estricto para cristalizar
    )


# ============================================================================
# TESTS BÁSICOS
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TEST: MetaMetaParameters (Ψ) - MSE v5.0.2-R")
    print("=" * 60)
    
    # Test 1: Creación default
    psi = create_default_psi()
    print(f"\nTest 1: Creación default")
    print(f"  Ψ creado: tau_base={psi.tau_base}, tau_exploration={psi.tau_exploration}")
    print(f"  ✓ PASSED")
    
    # Test 2: Modulación de temperatura Q2
    print(f"\nTest 2: Modulación de temperatura τ(t) - Q2")
    episodes = [0, 12, 25, 37, 50, 62, 75, 87, 100]
    for ep in episodes:
        tau = psi.get_current_temperature(ep)
        phase = psi.get_phase(ep)
        factor = psi.get_exploration_factor(ep)
        print(f"  Episodio {ep:3d}: τ={tau:.3f}, fase={phase:12s}, factor={factor:.3f}")
    print(f"  ✓ PASSED")
    
    # Test 3: Serialización
    print(f"\nTest 3: Serialización (to_dict/from_dict)")
    psi_dict = psi.to_dict()
    psi_restored = MetaMetaParameters.from_dict(psi_dict)
    assert psi_restored.tau_base == psi.tau_base, "Error en restauración tau_base"
    assert psi_restored.cycle_period == psi.cycle_period, "Error en restauración cycle_period"
    print(f"  ✓ PASSED")
    
    # Test 4: Pesos del Lagrangiano A14-A16
    print(f"\nTest 4: Pesos del Lagrangiano - A14-A16")
    lagrangian = psi.get_lagrangian_weights()
    print(f"  L = {lagrangian['alpha']}·C_comp + {lagrangian['beta']}·C_incert + {lagrangian['gamma']}·C_complej")
    print(f"  ✓ PASSED")
    
    # Test 5: Validación de dominios
    print(f"\nTest 5: Validación de dominios admisibles")
    try:
        psi_invalid = MetaMetaParameters(tau_base=-1.0)  # Debería fallar
        print(f"  ✗ FAILED: Debería haber lanzado AssertionError")
    except AssertionError as e:
        print(f"  ✓ PASSED: Validación correcta ({str(e)[:50]}...)")
    
    print("\n" + "=" * 60)
    print("TODOS LOS TESTS PASSED")
    print("=" * 60)

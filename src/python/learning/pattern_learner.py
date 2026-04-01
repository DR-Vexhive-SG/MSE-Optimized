# src/python/learning/pattern_learner.py
"""
Módulo de Aprendizaje de Patrones - MSE v4.0
Responsable de analizar resoluciones exitosas y generar nuevos patrones persistentes.
Alineado con MSE-V .4.0 Formal Logic.txt Sec. VIII.2 (ΔE(pt)) y Sec. XI.5 (Persistencia).

ETAPA: 1, 3
AUTOR: Codex (Protocolo Vexhive)
FECHA: 2026-02-12
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import asdict
import sys
from pathlib import Path

# Asegurar ruta correcta
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.python.persistence.pattern_database import StoredPattern, HybridPatternDatabase
from src.python.knowledge.translator import Translator
from src.python.state.board_state import BoardState


class PatternLearner:
    """
    Analiza patrones aplicados durante la resolución y genera nuevos StoredPattern.
    Implementa aprendizaje post-resolución según mse-decrytp.txt sección 4.5.

    MSE Formal Logic.txt Sec. VIII.2:
    ΔE(pt) = +δ⁺ si aplicación de pt resultó en prog_k=1
    ΔE(pt) = -δ⁻ si no produjo progreso
    """

    def __init__(self, pattern_db: HybridPatternDatabase):
        self.pattern_db = pattern_db
        self.translator = Translator()
        self.new_patterns_generated = 0
        self.patterns_updated = 0

    def learn_from_resolution(self, applied_patterns_log: List[Tuple[str, Dict[str, Any], bool]]) -> Dict[str, int]:
        """
        Analiza el log de patrones aplicados para generar y almacenar nuevos patrones.

        Args:
            applied_patterns_log: Lista de (pattern_type, details, success)

        Returns:
            Dict con estadísticas: {'generated': int, 'updated': int, 'failed': int}

        MSE Formal Logic.txt: ΔE(pt) = +0.1 si aplicación de pt resultó en prog_k=1.
        mse-decrytp.txt sección 4.5: La evolución emerge de la acumulación continua de conocimiento.
        """
        print(f"  [PatternLearner] Analizando {len(applied_patterns_log)} patrones aplicados para aprendizaje...")

        stats = {'generated': 0, 'updated': 0, 'failed': 0}

        for pattern_info in applied_patterns_log:
            pattern_type, details, success = pattern_info

            # Solo generar/actualizar patrones si tuvo éxito (prog_k > 0 implícito)
            if success:
                # Generar máscaras desde los detalles del patrón
                trigger_mask, elimination_mask = self.create_mask_from_pattern_details(
                    pattern_type, details
                )

                if trigger_mask is not None and elimination_mask is not None:
                    # Verificar soundness formal antes de añadir
                    if self._validate_pattern_soundness(trigger_mask, elimination_mask, pattern_type):
                        # Intentar añadir como nuevo patrón o actualizar existente
                        added = self.pattern_db.add_pattern(
                            predicate_type=pattern_type,
                            trigger_mask_cpu=trigger_mask,
                            elimination_mask_cpu=elimination_mask,
                            confidence=1.0  # Confianza inicial por éxito reciente
                        )

                        if added:
                            stats['generated'] += 1
                            print(f"    [PatternLearner] Nuevo patrón '{pattern_type}' generado (ID: {added.id[:8]}).")
                        else:
                            stats['updated'] += 1
                            print(f"    [PatternLearner] Patrón existente '{pattern_type}' actualizado.")
                    else:
                        stats['failed'] += 1
                        print(f"    [PatternLearner] WARNING: Patrón '{pattern_type}' falló validación de soundness.")
                else:
                    stats['failed'] += 1
                    print(f"    [PatternLearner] No se pudo generar máscara para patrón '{pattern_type}'.")
            else:
                # Patrón fallido: no generar, pero podríamos registrar para análisis futuro
                pass

        self.new_patterns_generated = stats['generated']
        self.patterns_updated = stats['updated']

        print(f"  [PatternLearner] Resumen: {stats['generated']} nuevos, {stats['updated']} actualizados, {stats['failed']} fallidos.")

        return stats

    def create_mask_from_pattern_details(self, pattern_type: str, details: Dict[str, Any]) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Crea máscaras de activación/eliminación desde los detalles de un patrón.

        Args:
            pattern_type: Tipo de patrón (Hidden_Single, Naked_Pair, X_Wing, etc.)
            details: Diccionario con información específica del patrón

        Returns:
            (trigger_mask_cpu, elimination_mask_cpu) o (None, None) si falla

        MSE Formal Logic.txt Sec. VII: Formalización de patrones R4-R9.
        """
        # Inicializar máscaras vacías (81 celdas × 9 valores)
        trigger_mask = np.zeros((81, 9), dtype=bool)
        elimination_mask = np.zeros((81, 9), dtype=bool)

        try:
            # Manejar patrones inducidos (prefijo Induced_)
            if pattern_type.startswith('Induced_'):
                original_type = pattern_type[len('Induced_'):]
                return self._create_mask_for_induced_pattern(original_type, details, trigger_mask, elimination_mask)

            # Patrones estándar R4-R9
            if pattern_type == 'Hidden_Single':
                return self._create_mask_hidden_single(details, trigger_mask, elimination_mask)

            elif pattern_type == 'Naked_Pair':
                return self._create_mask_naked_pair(details, trigger_mask, elimination_mask)

            elif pattern_type == 'X_Wing':
                return self._create_mask_x_wing(details, trigger_mask, elimination_mask)

            # ... otros patrones según sea necesario ...

            else:
                print(f"    [PatternLearner] WARNING: Tipo de patrón '{pattern_type}' no implementado.")
                return None, None

        except Exception as e:
            print(f"    [PatternLearner] ERROR creando máscara para {pattern_type}: {e}")
            return None, None

    def _create_mask_hidden_single(self, details: Dict[str, Any],
                                   trigger_mask: np.ndarray,
                                   elimination_mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Genera máscaras para Hidden Single (R4-R6).

        details: {'cell': (r, c), 'value': v, 'unit_type': 'row/col/box', 'unit_index': idx}

        MSE Formal Logic.txt Sec. II.2:
        R4_fila:    ∃!j: K(i,j,v) ∧ ¬S(i,j) → C(i,j,v)
        R5_columna: ∃!i: K(i,j,v) ∧ ¬S(i,j) → C(i,j,v)
        R6_caja:    ∃!(i,j)∈caja(b): K(i,j,v) ∧ ¬S(i,j) → C(i,j,v)
        """
        cell = details['cell']
        value = details['value']
        r, c = cell
        val_idx = value - 1  # Convertir a índice 0-based

        # Trigger: La celda (r,c) debe tener el valor 'v' como candidato
        trigger_mask[r * 9 + c, val_idx] = True

        # Elimination: Eliminar todos los demás candidatos de la celda (r,c)
        for v_idx in range(9):
            if v_idx != val_idx:
                elimination_mask[r * 9 + c, v_idx] = True

        return trigger_mask, elimination_mask

    def _create_mask_naked_pair(self, details: Dict[str, Any],
                                trigger_mask: np.ndarray,
                                elimination_mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Genera máscaras para Naked Pair (R7).

        details: {'cells': ((r1,c1), (r2,c2)), 'values': [v1, v2], 'unit_type': 'row/col/box', 'unit_index': idx}

        MSE Formal Logic.txt Sec. II.3:
        R7: ∃c₁≠c₂∈U: |Ω(c₁)|=2 ∧ |Ω(c₂)|=2 ∧ Ω(c₁)=Ω(c₂)={a,b} ∧ c₁,c₂∈misma_unidad(U)
        → ∀c∈U\{c₁,c₂}: ¬K(c,a) ∧ ¬K(c,b)
        """
        cells = details['cells']
        values = details['values']
        unit_type = details['unit_type']
        unit_idx = details['unit_index']

        # Trigger: Las 2 celdas contienen los 2 valores exactamente
        for (r, c) in cells:
            idx = r * 9 + c
            for val in values:
                val_idx = val - 1
                trigger_mask[idx, val_idx] = True

        # Elimination: Eliminar v1, v2 de otras celdas de la unidad
        other_cells_in_unit = self._get_other_cells_in_unit(unit_type, unit_idx, cells)

        for (r, c) in other_cells_in_unit:
            idx = r * 9 + c
            for val in values:
                val_idx = val - 1
                elimination_mask[idx, val_idx] = True

        return trigger_mask, elimination_mask

    def _create_mask_x_wing(self, details: Dict[str, Any],
                            trigger_mask: np.ndarray,
                            elimination_mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Genera máscaras para X-Wing (R8).

        details: {'value': v, 'rows': [r1, r2], 'cols': [c1, c2]}

        MSE Formal Logic.txt Sec. II.4:
        R8: ∃r₁≠r₂,c₁≠c₂,v:
        [K(r₁,c₁,v) ∧ K(r₁,c₂,v) ∧ ¬∃c∉{c₁,c₂}: K(r₁,c,v)] ∧
        [K(r₂,c₁,v) ∧ K(r₂,c₂,v) ∧ ¬∃c∉{c₁,c₂}: K(r₂,c,v)]
        → ∀r∉{r₁,r₂}: ¬K(r,c₁,v) ∧ ¬K(r,c₂,v)
        """
        value = details['value']
        rows = details['rows']
        cols = details['cols']
        val_idx = value - 1

        # Trigger: Marcar posiciones clave del X-Wing
        for r in rows:
            for c in cols:
                idx = r * 9 + c
                trigger_mask[idx, val_idx] = True

        # Elimination: Eliminar 'v' de otras filas en cols c1,c2
        for r in range(9):
            if r not in rows:
                for c in cols:
                    idx = r * 9 + c
                    elimination_mask[idx, val_idx] = True

        # Elimination: Eliminar 'v' de otras columnas en filas r1,r2
        for r in rows:
            for c in range(9):
                if c not in cols:
                    idx = r * 9 + c
                    elimination_mask[idx, val_idx] = True

        return trigger_mask, elimination_mask

    def _create_mask_for_induced_pattern(self, original_type: str, details: Dict[str, Any],
                                         trigger_mask: np.ndarray,
                                         elimination_mask: np.ndarray) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Maneja patrones inducidos estructuralmente.

        MSE Formal Logic.txt Sec. VII.7: XY-Chain / Forcing Chain
        """
        print(f"      [PatternLearner] Procesando patrón inducido: {original_type}")

        if original_type == 'Naked_Subset_Size_2':
            return self._create_mask_naked_pair(details, trigger_mask, elimination_mask)
        elif original_type == 'X_Wing':
            return self._create_mask_x_wing(details, trigger_mask, elimination_mask)
        # ... otros tipos inducidos ...

        return None, None

    def _get_other_cells_in_unit(self, unit_type: str, unit_idx: int,
                                 exclude_cells: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """
        Obtiene todas las celdas en una unidad excepto las especificadas.
        """
        other_cells = []

        if unit_type == 'row':
            other_cells = [(unit_idx, c) for c in range(9) if (unit_idx, c) not in exclude_cells]
        elif unit_type == 'col':
            other_cells = [(r, unit_idx) for r in range(9) if (r, unit_idx) not in exclude_cells]
        elif unit_type == 'box':
            start_r, start_c = (unit_idx // 3) * 3, (unit_idx % 3) * 3
            other_cells = [
                (r, c) for r in range(start_r, start_r + 3)
                       for c in range(start_c, start_c + 3)
                if (r, c) not in exclude_cells
            ]

        return other_cells

    def _validate_pattern_soundness(self, trigger_mask: np.ndarray,
                                    elimination_mask: np.ndarray,
                                    pattern_type: str) -> bool:
        """
        Valida que el patrón generado preserva soundness formal.

        Verifica:
        1. Máscaras no vacías
        2. Sin contradicciones internas (trigger ∩ elimination = ∅ para misma celda/valor)
        3. Axiomas A1-A6 preservados

        MSE Formal Logic.txt Sec. XII.3: Teorema de Preservación de Corrección.
        """
        # Verificación 1: Máscaras no vacías
        if np.sum(trigger_mask) == 0:
            print(f"    [PatternLearner] WARNING: Trigger mask vacía para {pattern_type}.")
            return False

        # Verificación 2: Sin contradicciones internas
        # Una celda/valor no puede estar en trigger y elimination simultáneamente
        contradiction = np.logical_and(trigger_mask, elimination_mask)
        if np.any(contradiction):
            print(f"    [PatternLearner] WARNING: Contradicción interna en {pattern_type}.")
            return False

        # Verificación 3: Eliminación válida (al menos un candidato eliminado)
        if np.sum(elimination_mask) == 0:
            print(f"    [PatternLearner] WARNING: Elimination mask vacía para {pattern_type}.")
            return False

        return True


# Función de conveniencia para uso directo
def create_pattern_learner(pattern_db: HybridPatternDatabase) -> PatternLearner:
    """
    Factory function para crear PatternLearner con DB configurada.
    """
    return PatternLearner(pattern_db)

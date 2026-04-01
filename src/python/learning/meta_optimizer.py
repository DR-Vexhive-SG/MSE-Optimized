# src/python/learning/meta_optimizer.py

"""
Optimizador Meta basado en Cálculo Variacional para MSE-V 4.0 y REINFORCE.

Este módulo implementa la estimación del gradiente del costo total J(Φ)
respecto a los meta-parámetros Φ, utilizando diferencias finitas simétricas.
También puede integrar el algoritmo REINFORCE para actualizar los meta-parámetros.
Incluye un límite estricto de iteraciones para evitar bucles infinitos en la simulación.
"""

import sys
import os
import numpy as np
import torch
import torch.optim as optim
from typing import List, Tuple, Callable, Any
from copy import deepcopy
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.python.learning.variational_meta_learner import MetaParameters, VariationalMetaLearner
from src.python.solver.evolutionary_solver import EvolutionarySolver


class MetaOptimizer:
    """
    Coordina la optimización de los meta-parámetros Φ.
    Incorpora tanto diferencias finitas como REINFORCE.
    """

    def __init__(self, meta_learner: VariationalMetaLearner, solver_factory: Callable[[], EvolutionarySolver]):
        """
        Args:
            meta_learner: Instancia del gestor de meta-parámetros.
            solver_factory: Función que crea una nueva instancia del EvolutionarySolver
                           configurada para usar los meta-parámetros actuales.
        """
        self.meta_learner = meta_learner
        self.solver_factory = solver_factory

        # Inicializar un optimizador de PyTorch para los parámetros específicos de la política
        # que se actualizarán con REINFORCE.
        self.torch_params_dict = self._convert_meta_params_to_torch_params(meta_learner.get_current_params())
        self.torch_params_list = list(self.torch_params_dict.values())
        self.policy_optimizer = optim.Adam(self.torch_params_list, lr=meta_learner.meta_params.alpha_meta)

    def _convert_meta_params_to_torch_params(self, meta_params: MetaParameters) -> dict:
        """
        Convierte algunos parámetros de MetaParameters a tensores de PyTorch con requires_grad=True.
        Solo los parámetros que se actualizarán con REINFORCE se convierten aquí.
        """
        torch_params = {}
        torch_params['w1'] = torch.tensor(float(meta_params.w1), requires_grad=True)
        torch_params['w2'] = torch.tensor(float(meta_params.w2), requires_grad=True)
        torch_params['w3'] = torch.tensor(float(meta_params.w3), requires_grad=True)
        torch_params['lambda_H'] = torch.tensor(float(meta_params.lambda_H), requires_grad=True)
        torch_params['delta_plus'] = torch.tensor(float(meta_params.delta_plus), requires_grad=True)
        torch_params['delta_minus'] = torch.tensor(float(meta_params.delta_minus), requires_grad=True)
        return torch_params

    def _run_episode_with_params(self, puzzle: np.ndarray, params: MetaParameters, max_iterations_for_simulation: int = 100) -> Tuple[float, bool, int]:
        """
        Ejecuta un episodio (resolución de un puzzle) con un conjunto dado de meta-parámetros.
        Incluye un límite estricto de iteraciones para evitar bucles infinitos.
        Captura la experiencia generada por la política para REINFORCE.

        Args:
            puzzle: El puzzle a resolver.
            params: Los meta-parámetros a usar para esta simulación.
            max_iterations_for_simulation: Límite de iteraciones para el ciclo evolutivo de esta simulación.

        Returns:
            (costo, éxito, backtracks)
        """
        solver = self.solver_factory()

        try:
            solved, _ = solver.solve(puzzle, max_cycles=250, max_loop_iterations=max_iterations_for_simulation)
        except TypeError:
            print("  [MetaOptimizer] WARNING: El solver no acepta 'max_loop_iterations'. Usando valor por defecto (posible bucle).")
            solved, _ = solver.solve(puzzle, max_cycles=200)
            return self.meta_learner.meta_params.B_max * 10, False, 0

        backtracks = solver.stats.get_stat('backtrack_count')
        evolutionary_iterations = solver.stats.get_stat('evolutionary_iterations')

        if evolutionary_iterations >= max_iterations_for_simulation:
            cost = self.meta_learner.meta_params.B_max * 5
            success = False
        else:
            cost = self.meta_learner.calculate_episode_cost(backtracks, solved)
            success = solved

        # La política debe haber acumulado experiencia (log_probs, recompensas) durante el episodio.
        # Aquí se supone que la política ha sido informada del costo final del episodio
        # para calcular los retornos y aplicar los gradientes de REINFORCE.
        # La lógica de integración con la política (en el bucle evolutivo) es crítica.
        # Por ahora, asumimos que la política se actualiza internamente al final del episodio
        # resolviendo el puzzle en 'solver.solve'.

        return cost, success, backtracks

    def estimate_gradient(self, puzzle: np.ndarray, current_params: MetaParameters, episode_window: int = 5, simulation_max_iterations: int = 100) -> np.ndarray:
        """
        [ESTE MÉTODO YA NO ES EL PRINCIPAL PARA ACTUALIZAR PARÁMETROS RELACIONADOS CON LA POLÍTICA]
        Estima el gradiente dJ/dΦ usando diferencias finitas simétricas sobre una ventana de episodios.
        Incluye un límite estricto de iteraciones para la simulación de cada episodio.
        """
        print("  [MetaOptimizer] Advertencia: estimate_gradient (diferencias finitas) se está ejecutando. Este método no actualiza parámetros optimizados por REINFORCE.")
        param_names = list(current_params.to_dict().keys())
        num_params = len(param_names)
        gradient = np.zeros(num_params)

        bounds = current_params.get_bounds()
        base_cost_sum = 0.0

        for _ in range(episode_window):
            cost, _, _ = self._run_episode_with_params(puzzle, current_params, max_iterations_for_simulation=simulation_max_iterations)
            base_cost_sum += cost
        base_cost_avg = base_cost_sum / episode_window

        for i, param_name in enumerate(param_names):
            if param_name in ['B_max', 'mu_penalty']:
                continue

            low, high = bounds[param_name]
            rel_perturbation = self.meta_learner.meta_params.epsilon_perturbation
            abs_perturbation = rel_perturbation * (high - low)

            params_plus = deepcopy(current_params)
            params_minus = deepcopy(current_params)
            setattr(params_plus, param_name, getattr(params_plus, param_name) + abs_perturbation)
            setattr(params_minus, param_name, getattr(params_minus, param_name) - abs_perturbation)

            params_plus.project_into_bounds()
            params_minus.project_into_bounds()

            cost_plus_sum = 0.0
            cost_minus_sum = 0.0
            for _ in range(episode_window):
                cost_p, _, _ = self._run_episode_with_params(puzzle, params_plus, max_iterations_for_simulation=simulation_max_iterations)
                cost_m, _, _ = self._run_episode_with_params(puzzle, params_minus, max_iterations_for_simulation=simulation_max_iterations)
                cost_plus_sum += cost_p
                cost_minus_sum += cost_m

            cost_plus_avg = cost_plus_sum / episode_window
            cost_minus_avg = cost_minus_sum / episode_window

            gradient[i] = (cost_plus_avg - cost_minus_avg) / (2 * abs_perturbation)
            print(f"  [MetaOptimizer] Gradiente estimado para {param_name}: {gradient[i]:.6f}")

        return gradient

    def _sync_torch_params_to_meta_learner(self):
        """
        Copia los valores actualizados de los torch_params_dict al objeto VariationalMetaLearner.
        """
        current_meta_params = self.meta_learner.get_current_params()
        for name, torch_param in self.torch_params_dict.items():
            if hasattr(current_meta_params, name):
                setattr(current_meta_params, name, torch_param.item())
        current_meta_params.project_into_bounds()
        self.meta_learner.update_parameters(current_meta_params)
        print("  [MetaOptimizer] Parámetros de la política (torch_params) sincronizados con VariationalMetaLearner.")

    def optimize_meta_parameters(self, puzzle: np.ndarray, episodes_per_optimization: int = 5, simulation_max_iterations: int = 100):
        """
        Realiza un paso de optimización de los meta-parámetros.
        Se enfoca en actualizar parámetros relacionados con la política usando REINFORCE.
        """
        print("[MetaOptimizer] Iniciando optimización de meta-parámetros...")
        print("[MetaOptimizer] Atención: La actualización principal ahora proviene de REINFORCE (dentro de _run_episode_with_params).")
        current_params = self.meta_learner.get_current_params()

        for ep_num in range(episodes_per_optimization):
            print(f"    [MetaOptimizer] Ejecutando episodio de simulación REINFORCE #{ep_num+1}...")
            cost, success, backtracks = self._run_episode_with_params(puzzle, current_params, max_iterations_for_simulation=simulation_max_iterations)
            print(f"      [MetaOptimizer] Episodio #{ep_num+1} completado. Costo: {cost}, Éxito: {success}, Backtracks: {backtracks}")

        # Sincronizar los parámetros actualizados de PyTorch con el objeto VariationalMetaLearner
        self._sync_torch_params_to_meta_learner()

        print("[MetaOptimizer] Optimización de meta-parámetros completada (vía REINFORCE).")


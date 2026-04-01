# src/python/market/meta/trading_meta_learner.py
"""
Trading Meta Learner - MSE v5.0.2-R
===================================

Optimización REINFORCE para estrategia y patrones.
Conexión formal: MSE-V Sec. XI.3 (Estimación de Gradiente), math_patch.txt Sec. 2.4

Niveles de Autonomía:
- N0: Supervisado ✅ Completado
- N1: Semi-autónomo ✅ QC v1.0
- N2: Descubrimiento guiado ✅ DÍA 1
- N3: Autonomía con veto ⏳ ESTA IMPLEMENTACIÓN
"""

import numpy as np
import torch
import torch.nn.functional as F
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
import sys
import time

# Asegurar paths
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.python.learning.variational_meta_learner import MetaParameters
from src.python.market.market_pattern_database import MarketPatternDatabase, MarketStoredPattern


@dataclass
class StrategyEpisode:
    """
    Episodio de estrategia para REINFORCE.
    
    Atributos:
        timestamp: Timestamp del episodio
        strategy: Estrategia seleccionada
        log_prob: Log-probabilidad de la selección
        regime: Régimen de mercado
        patterns_used: Patrones utilizados
        pnl: PnL del episodio
        success: True si PnL > 0
    """
    timestamp: float
    strategy: str
    log_prob: torch.Tensor
    regime: str
    patterns_used: List[str]
    pnl: float = 0.0
    success: bool = False


class TradingMetaLearner:
    """
    Actualiza estrategia y E(pt) vía REINFORCE.
    
    Formalización (MSE-V Sec. XI.3):
      ∇_Φ J = Σ_t [∇_Φ log π_Φ(strategy_t | state_t) · (G_t - b)]
    
    Donde:
      - G_t = retorno acumulado desde t hasta fin de episodio
      - b = baseline (retorno promedio de últimos 10 episodios)
      - Φ incluye: temperature, strategy_weights, E_pt_decay
    
    update_strategy_policy():
      Calcula gradiente de política y actualiza Φ
    
    update_pattern_effectiveness():
      Actualiza E(pt) con δ⁺/δ⁻ (cristalización si E > 0.95)
    
    Criterio de Éxito:
      - Φ converge en ≤50 episodios
      - E(pt) de patrones rentables >0.70
    """
    
    def __init__(self, pattern_db: Optional[MarketPatternDatabase] = None,
                 baseline_decay: float = 0.99,
                 learning_rate: float = 0.01):
        """
        Inicializar meta learner.
        
        Args:
            pattern_db: Base de datos de patrones
            baseline_decay: Decaimiento exponencial para baseline
            learning_rate: Tasa de aprendizaje para Φ
        """
        self.pattern_db = pattern_db or MarketPatternDatabase()
        self.baseline_decay = baseline_decay
        self.learning_rate = learning_rate
        
        # Historial de episodios
        self.episodes: List[StrategyEpisode] = []
        self.log_probs_history: List[torch.Tensor] = []
        self.rewards_history: List[float] = []
        
        # Baseline para REINFORCE
        self.baseline = 0.0
        
        # Meta-parámetros
        self.meta_params = MetaParameters()
        
        # Weights de estrategia (inicialmente uniformes)
        self.strategy_weights = {
            'BULL': 1.0,
            'BEAR': 1.0,
            'LATERAL': 1.0,
            'MARKET_NEUTRAL': 1.0
        }

        # Estadísticas
        self.stats = {
            'total_episodes': 0,
            'total_updates': 0,
            'convergence_episode': None,
            'avg_win_rate': 0.0
        }

        # 1C.12: Cargar política persistente si existe
        self.load_policy()

    def save_policy(self, path: str = "data/patterns/meta_policy.pkl"):
        """
        1C.12: Guardar strategy_weights y baseline para persistencia.
        """
        from pathlib import Path
        import pickle

        policy_path = Path(path)
        policy_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            'strategy_weights': self.strategy_weights,
            'baseline': self.baseline,
            'meta_params': self.meta_params.to_dict(),
            'stats': self.stats
        }

        try:
            with open(policy_path, 'wb') as f:
                pickle.dump(data, f)

            print(f"[MetaLearner] ✅ Policy saved to {policy_path}")
            print(f"[MetaLearner] Strategy weights: {self.strategy_weights}")
        except Exception as e:
            print(f"[MetaLearner] ❌ Error saving policy: {e}")

    def load_policy(self, path: str = "data/patterns/meta_policy.pkl"):
        """
        1C.12: Cargar strategy_weights y baseline desde archivo.
        """
        from pathlib import Path
        import pickle

        policy_path = Path(path)

        if not policy_path.exists():
            print(f"[MetaLearner] ℹ️ No saved policy found, using defaults")
            return False

        try:
            with open(policy_path, 'rb') as f:
                data = pickle.load(f)

            self.strategy_weights = data['strategy_weights']
            self.baseline = data['baseline']
            self.meta_params = MetaParameters.from_dict(data['meta_params'])
            self.stats.update(data.get('stats', {}))

            print(f"[MetaLearner] ✅ Policy loaded from {policy_path}")
            print(f"[MetaLearner] Strategy weights: {self.strategy_weights}")
            return True

        except Exception as e:
            print(f"[MetaLearner] ❌ Error loading policy: {e}")
            return False
    
    def select_strategy(self, state_features: Dict[str, Any],
                       regime: str,
                       patterns: List[MarketStoredPattern]) -> Tuple[str, torch.Tensor]:
        """
        Seleccionar estrategia vía softmax (estocástico para REINFORCE).
        
        Formalización:
          score_BULL = Σ E(pt) para pt ∈ patterns si pt.regime == BULL
          score_BEAR = Σ E(pt) para pt ∈ patterns si pt.regime == BEAR
          score_LATERAL = Σ E(pt) para pt ∈ patterns si pt.regime == LATERAL
          score_NEUTRAL = 0.50  # Base por defecto
        
        probs = softmax([score_BULL, score_BEAR, score_LATERAL, score_NEUTRAL] / τ)
        strategy = choice([BULL, BEAR, LATERAL, NEUTRAL], p=probs)
        
        Args:
            state_features: Características del estado
            regime: Régimen actual
            patterns: Patrones disponibles
        
        Returns:
            Tuple[str, torch.Tensor]: Estrategia seleccionada, log_prob
        """
        # Calcular scores por estrategia
        scores = {
            'BULL': 0.0,
            'BEAR': 0.0,
            'LATERAL': 0.0,
            'MARKET_NEUTRAL': 0.50  # Base
        }
        
        # Sumar E(pt) por estrategia
        for pattern in patterns:
            if pattern.regime.value == 'bull':
                scores['BULL'] += pattern.confidence
            elif pattern.regime.value == 'bear':
                scores['BEAR'] += pattern.confidence
            elif pattern.regime.value == 'lateral':
                scores['LATERAL'] += pattern.confidence
        
        # Aplicar weights de estrategia
        for strategy in scores:
            scores[strategy] *= self.strategy_weights.get(strategy, 1.0)
        
        # Convertir a tensor
        strategy_names = ['BULL', 'BEAR', 'LATERAL', 'MARKET_NEUTRAL']
        scores_tensor = torch.tensor([scores[s] for s in strategy_names], dtype=torch.float32)
        
        # Aplicar temperatura y softmax
        tau = self.meta_params.temperature
        logits = scores_tensor / tau
        probs = F.softmax(logits, dim=-1)
        
        # Muestrear estrategia (estocástico para gradiente)
        strategy_idx = torch.multinomial(probs, num_samples=1).item()
        selected_strategy = strategy_names[strategy_idx]

        # Calcular log_prob para REINFORCE
        # FIX: Add epsilon-floor to prevent log(0) or log(1) which causes zero gradients
        epsilon = 1e-6
        clipped_prob = torch.clamp(probs[strategy_idx], epsilon, 1.0 - epsilon)
        log_prob = torch.log(clipped_prob)

        # [DEBUG] Log selection and log_prob recording
        print(f"[MetaLearner DEBUG] select_strategy: selected={selected_strategy}, log_prob={log_prob.item():.4f}, prob={probs[strategy_idx].item():.6f}")
        print(f"[MetaLearner DEBUG] log_probs_history length BEFORE: {len(self.log_probs_history)}")

        # NOTA: REMOVED self.strategy_weights[selected_strategy] *= 1.01
        # FIX: This was causing unbounded weight growth. REINFORCE gradients should be the ONLY update mechanism.

        return selected_strategy, log_prob
    
    def record_episode(self, strategy: str, log_prob: torch.Tensor,
                      regime: str, patterns_used: List[str],
                      pnl: float):
        """
        Registrar episodio para aprendizaje.

        Args:
            strategy: Estrategia seleccionada
            log_prob: Log-probabilidad de selección
            regime: Régimen de mercado
            patterns_used: Patrones utilizados
            pnl: PnL del episodio
        """
        episode = StrategyEpisode(
            timestamp=time.time(),
            strategy=strategy,
            log_prob=log_prob,
            regime=regime,
            patterns_used=patterns_used,
            pnl=pnl,
            success=pnl > 0
        )

        self.episodes.append(episode)
        self.log_probs_history.append(log_prob)
        self.rewards_history.append(pnl)
        self.stats['total_episodes'] += 1

        # [DEBUG] Log episode recording
        print(f"[MetaLearner DEBUG] record_episode: strategy={strategy}, pnl={pnl:.2f}, log_probs_history len={len(self.log_probs_history)}, rewards_history len={len(self.rewards_history)}")

        # Actualizar baseline
        self._update_baseline(pnl)
    
    def _update_baseline(self, reward: float):
        """Actualizar baseline con promedio móvil exponencial."""
        self.baseline = self.baseline_decay * self.baseline + (1 - self.baseline_decay) * reward
    
    def calculate_returns(self, gamma: float = 1.0) -> torch.Tensor:
        """
        Calcular retornos acumulados G_t.
        
        G_T = R_T
        G_t = R_t + gamma * G_{t+1}
        
        Args:
            gamma: Factor de descuento (default 1.0 para trading)
        
        Returns:
            Tensor de retornos
        """
        if not self.rewards_history:
            return torch.tensor([], dtype=torch.float32)
        
        returns = []
        G = 0.0
        
        for r in reversed(self.rewards_history):
            G = r + gamma * G
            returns.insert(0, G)
        
        return torch.tensor(returns, dtype=torch.float32)
    
    def update_strategy_policy(self, meta_params: Optional[MetaParameters] = None) -> Dict[str, float]:
        """
        Actualizar política de estrategia vía REINFORCE.

        Fórmula:
          ∇_Φ J = Σ_t [∇_Φ log π_Φ(strategy_t | state_t) · (G_t - b)]

        Args:
            meta_params: Meta-parámetros a actualizar (default: self.meta_params)

        Returns:
            Diccionario con gradientes aproximados
        """
        # [DEBUG] Log update process start
        print(f"[MetaLearner DEBUG] update_strategy_policy called")
        print(f"[MetaLearner DEBUG] log_probs_history length: {len(self.log_probs_history)}")
        print(f"[MetaLearner DEBUG] rewards_history length: {len(self.rewards_history)}")
        print(f"[MetaLearner DEBUG] episodes length: {len(self.episodes)}")
        print(f"[MetaLearner DEBUG] strategy_weights BEFORE method: {self.strategy_weights}")

        if not self.log_probs_history:
            print(f"[MetaLearner DEBUG] EXIT: log_probs_history is empty")
            return {}

        if len(self.log_probs_history) < 2:
            print(f"[MetaLearner DEBUG] WARNING: Only {len(self.log_probs_history)} episodes, waiting for more data")
            # Don't exit - still process with available data

        # Calcular retornos
        returns = self.calculate_returns()

        if returns.numel() == 0:
            print(f"[MetaLearner DEBUG] EXIT: returns is empty")
            return {}

        print(f"[MetaLearner DEBUG] returns: {returns}, numel: {returns.numel()}")

        # Calcular advantages (G - b)
        advantages = returns - self.baseline

        print(f"[MetaLearner DEBUG] baseline: {self.baseline:.4f}")
        print(f"[MetaLearner DEBUG] advantages: {advantages}, mean: {advantages.mean().item():.4f}")

        # Calcular pérdida REINFORCE
        log_probs = torch.stack(self.log_probs_history)
        loss = -(log_probs * advantages.detach()).mean()

        print(f"[MetaLearner DEBUG] loss: {loss.item():.6f}")
        print(f"[MetaLearner DEBUG] log_probs: {log_probs}, mean: {log_probs.mean().item():.4f}")

        # FIX: Calculate per-strategy gradients based on actual episode advantages
        # Group advantages by strategy
        strategy_advantages: Dict[str, List[float]] = {s: [] for s in self.strategy_weights}

        for i, episode in enumerate(self.episodes[-len(advantages):]):  # Match episodes to advantages
            if i < len(advantages):
                # FIX: Convert strategy to uppercase to match strategy_weights keys
                strategy_key = episode.strategy.upper()
                if strategy_key in strategy_advantages:
                    strategy_advantages[strategy_key].append(advantages[i].item())

        print(f"[MetaLearner DEBUG] strategy_advantages: {strategy_advantages}")

        # Calcular gradientes por estrategia
        gradients = {}
        for strategy in self.strategy_weights:
            if strategy_advantages[strategy]:
                # Gradiente proporcional al advantage promedio de esta estrategia
                avg_adv = np.mean(strategy_advantages[strategy])
                gradients[f'weight_{strategy}'] = avg_adv * self.learning_rate
                print(f"[MetaLearner DEBUG] {strategy}: avg_advantage={avg_adv:.4f}, gradient={gradients[f'weight_{strategy}']:.6f}")
            else:
                gradients[f'weight_{strategy}'] = 0.0
                print(f"[MetaLearner DEBUG] {strategy}: no episodes, gradient=0.0")

        # [DEBUG] Log before weight update
        print(f"[MetaLearner DEBUG] strategy_weights BEFORE update: {self.strategy_weights}")
        print(f"[MetaLearner DEBUG] gradients: {gradients}")

        # Actualizar weights
        for strategy, grad in gradients.items():
            strategy_name = strategy.replace('weight_', '')
            old_weight = self.strategy_weights[strategy_name]
            self.strategy_weights[strategy_name] += grad
            new_weight = self.strategy_weights[strategy_name]
            # Clamp para estabilidad (rangos más amplios para permitir aprendizaje)
            self.strategy_weights[strategy_name] = max(0.1, min(10.0, self.strategy_weights[strategy_name]))
            clamped_weight = self.strategy_weights[strategy_name]
            delta = clamped_weight - old_weight
            print(f"[MetaLearner DEBUG] {strategy_name}: {old_weight:.6f} + {grad:.6f} = {new_weight:.6f} (clamped: {clamped_weight:.6f}, Δ={delta:+.6f})")

        # [DEBUG] Log after weight update
        print(f"[MetaLearner DEBUG] strategy_weights AFTER: {self.strategy_weights}")

        # Actualizar meta-parámetros si se proporcionan
        if meta_params:
            self._update_meta_params(meta_params, loss, advantages)

        # Actualizar estadísticas
        self.stats['total_updates'] += 1

        # Verificar convergencia
        if self.stats['total_episodes'] >= 50 and self.stats['convergence_episode'] is None:
            if abs(loss.item()) < 0.01:
                self.stats['convergence_episode'] = self.stats['total_episodes']

        # Limpiar historial
        self.log_probs_history.clear()
        self.rewards_history.clear()

        return gradients
    
    def _update_meta_params(self, meta_params: MetaParameters,
                           loss: torch.Tensor,
                           advantages: torch.Tensor):
        """
        Actualizar meta-parámetros Φ según gradientes.
        
        Args:
            meta_params: Meta-parámetros a actualizar
            loss: Pérdida REINFORCE
            advantages: Advantages para cada episodio
        """
        # Actualizar temperature (exploración vs explotación)
        avg_advantage = advantages.mean().item()
        if avg_advantage > 0:
            # Éxito → reducir exploración
            meta_params.temperature = max(0.1, meta_params.temperature * 0.99)
        else:
            # Fracaso → aumentar exploración
            meta_params.temperature = min(5.0, meta_params.temperature * 1.01)
        
        # Actualizar delta_plus/delta_minus según win rate
        win_rate = sum(1 for e in self.episodes[-10:] if e.success) / max(1, len(self.episodes[-10:]))
        if win_rate > 0.6:
            # Alta win rate → aumentar δ⁺ (reforzar éxitos)
            meta_params.delta_plus = min(0.2, meta_params.delta_plus * 1.01)
        elif win_rate < 0.4:
            # Baja win rate → aumentar δ⁻ (penalizar fracasos)
            meta_params.delta_minus = min(0.3, meta_params.delta_minus * 1.01)
    
    def update_pattern_effectiveness(self, pattern_id: str, pnl_pct: float,
                                    success_threshold: float = 0.0,
                                    meta_params: Optional[MetaParameters] = None):
        """
        Actualizar E(pt) según PnL proporcional (REINFORCE 1B.8).

        Fórmula (1B.8 Specification):
          SI pnl_pct > success_threshold:
            reward_factor = min(2.0, 1.0 + pnl_pct / 0.03)
            E_pt ← min(1.0, E_pt + δ⁺ × reward_factor)
          SINO SI pnl_pct < 0:
            penalty_factor = min(2.0, 1.0 + |pnl_pct| / 0.03)
            E_pt ← max(0.1, E_pt - δ⁻ × penalty_factor)

          SI E_pt > 0.95: patrón.cristalizado = True

        Args:
            pattern_id: ID del patrón
            pnl_pct: PnL porcentual en decimal (ej: 0.05 = 5%)
            success_threshold: Umbral para considerar éxito (default: 0.0)
            meta_params: Meta-parámetros para δ⁺/δ⁻
        """
        if meta_params is None:
            meta_params = self.meta_params

        # Buscar patrón en DB
        for pattern in self.pattern_db.stored_patterns:
            if pattern.id == pattern_id:
                # Store initial confidence for logging
                initial_conf = pattern.confidence
                
                # 1B.8: REINFORCE proporcional al PnL
                if pnl_pct > success_threshold:
                    # Éxito: reward factor proporcional al PnL
                    reward_factor = min(2.0, 1.0 + pnl_pct / 0.03)
                    pattern.confidence = min(
                        meta_params.epsilon_max,
                        pattern.confidence + meta_params.delta_plus * reward_factor
                    )
                elif pnl_pct < 0:
                    # Fracaso: penalty factor proporcional a la pérdida
                    penalty_factor = min(2.0, 1.0 + abs(pnl_pct) / 0.03)
                    pattern.confidence = max(
                        meta_params.epsilon_min,
                        pattern.confidence - meta_params.delta_minus * penalty_factor
                    )

                # [DEBUG] Log pattern update
                print(f"[MetaLearner DEBUG] Pattern {pattern_id}: confidence {initial_conf:.3f} → {pattern.confidence:.3f} (Δ={pattern.confidence - initial_conf:+.3f}), pnl_pct={pnl_pct:+.4f}")

                # Verificar cristalización (Q4) - 1D.5 DEBUG: Revert to 1B.16 baseline (0.95)
                if pattern.confidence > 0.95 and not pattern.crystallized:
                    pattern.crystallized = True
                    pattern.is_soft = False
                    print(f"[MetaLearner DEBUG] Pattern {pattern_id}: CRYSTALLIZED!")

                break

        # Actualizar estadísticas
        self.stats['avg_win_rate'] = sum(1 for e in self.episodes if e.success) / max(1, len(self.episodes))
    
    def get_strategy_probs(self, patterns: List[MarketStoredPattern]) -> Dict[str, float]:
        """
        Obtener probabilidades actuales de estrategias.
        
        Args:
            patterns: Patrones disponibles
        
        Returns:
            Diccionario strategy → probabilidad
        """
        scores = {
            'BULL': 0.0,
            'BEAR': 0.0,
            'LATERAL': 0.0,
            'MARKET_NEUTRAL': 0.50
        }
        
        for pattern in patterns:
            if pattern.regime.value == 'bull':
                scores['BULL'] += pattern.confidence
            elif pattern.regime.value == 'bear':
                scores['BEAR'] += pattern.confidence
            elif pattern.regime.value == 'lateral':
                scores['LATERAL'] += pattern.confidence
        
        # Aplicar weights
        for strategy in scores:
            scores[strategy] *= self.strategy_weights.get(strategy, 1.0)
        
        # Softmax con temperatura
        strategy_names = ['BULL', 'BEAR', 'LATERAL', 'MARKET_NEUTRAL']
        scores_tensor = torch.tensor([scores[s] for s in strategy_names], dtype=torch.float32)
        tau = self.meta_params.temperature
        probs = F.softmax(scores_tensor / tau, dim=-1)
        
        return {name: prob.item() for name, prob in zip(strategy_names, probs)}
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de aprendizaje."""
        return {
            **self.stats,
            'baseline': self.baseline,
            'temperature': self.meta_params.temperature,
            'strategy_weights': self.strategy_weights.copy(),
            'strategy_probs': self.get_strategy_probs([]),
            'episodes_cached': len(self.episodes)
        }
    
    def reset(self):
        """Reiniciar estado para nuevo episodio."""
        self.log_probs_history.clear()
        self.rewards_history.clear()


# ============================================================================
# TESTS
# ============================================================================

if __name__ == "__main__":
    print("="*70)
    print("TEST: Trading Meta Learner - MSE v5.0.2-R N3")
    print("="*70)
    
    # Test 1: Crear meta learner
    print("\nTest 1: Crear TradingMetaLearner")
    meta_learner = TradingMetaLearner()
    print(f"  Baseline decay: {meta_learner.baseline_decay}")
    print(f"  Learning rate: {meta_learner.learning_rate}")
    print("  ✅ PASSED")
    
    # Test 2: Seleccionar estrategia
    print("\nTest 2: Seleccionar estrategia (softmax estocástico)")
    from src.python.market.market_pattern_database import MarketStoredPattern, create_builtin_patterns
    from src.python.market.axioms import MarketRegime
    
    patterns = create_builtin_patterns()
    strategy, log_prob = meta_learner.select_strategy({}, 'lateral', patterns)
    
    print(f"  Estrategia: {strategy}")
    print(f"  Log prob: {log_prob.item():.4f}")
    assert strategy in ['BULL', 'BEAR', 'LATERAL', 'MARKET_NEUTRAL']
    print("  ✅ PASSED")
    
    # Test 3: Registrar episodio
    print("\nTest 3: Registrar episodio")
    meta_learner.record_episode(strategy, log_prob, 'lateral', ['range_buy_low'], pnl=100.0)
    print(f"  Episodios: {len(meta_learner.episodes)}")
    print(f"  Baseline: {meta_learner.baseline:.2f}")
    print("  ✅ PASSED")
    
    # Test 4: Actualizar política REINFORCE
    print("\nTest 4: Actualizar política REINFORCE")
    # Registrar más episodios para tener datos
    for i in range(10):
        s, lp = meta_learner.select_strategy({}, 'lateral', patterns)
        pnl = np.random.normal(50, 100)  # PnL aleatorio
        meta_learner.record_episode(s, lp, 'lateral', [], pnl=pnl)
    
    gradients = meta_learner.update_strategy_policy()
    print(f"  Gradientes: {list(gradients.keys())}")
    print(f"  Updates: {meta_learner.stats['total_updates']}")
    print("  ✅ PASSED")
    
    # Test 5: Actualizar E(pt) con REINFORCE proporcional (1B.8)
    print("\nTest 5: Actualizar E(pt) con REINFORCE proporcional (1B.8)")
    
    # Agregar patrón a la DB del meta_learner para test
    from src.python.market.market_pattern_database import MarketStoredPattern, create_builtin_patterns
    from src.python.market.axioms import MarketRegime
    
    test_patterns = create_builtin_patterns()
    if test_patterns:
        # Agregar patrón a la DB del meta_learner
        meta_learner.pattern_db.stored_patterns.extend(test_patterns)
        
        pattern_id = test_patterns[0].id
        initial_conf = test_patterns[0].confidence
        print(f"  E(pt) inicial: {initial_conf:.3f}")

        # Simular éxitos con PnL positivo
        for i in range(5):
            meta_learner.update_pattern_effectiveness(pattern_id, pnl_pct=0.05)  # 5% PnL

        # Simular fracaso con pérdida
        meta_learner.update_pattern_effectiveness(pattern_id, pnl_pct=-0.02)  # -2% PnL

        final_conf = test_patterns[0].confidence
        cristalizado = test_patterns[0].crystallized
        print(f"  E(pt) final: {final_conf:.3f}")
        print(f"  Cristalizado: {cristalizado}")
        assert final_conf > initial_conf, f"E(pt) debe aumentar con éxitos ({initial_conf:.3f} → {final_conf:.3f})"
        print("  ✅ PASSED")
    
    # Test 6: Estadísticas
    print("\nTest 6: Estadísticas de aprendizaje")
    stats = meta_learner.get_stats()
    print(f"  Total episodios: {stats['total_episodes']}")
    print(f"  Win rate: {stats['avg_win_rate']:.1%}")
    print(f"  Temperatura: {stats['temperature']:.3f}")
    print(f"  Strategy probs: {stats['strategy_probs']}")
    print("  ✅ PASSED")
    
    print("\n" + "="*70)
    print("TESTS DE TRADING META LEARNER PASSED")
    print("="*70)

# MSE-Optimized

**Multi-agent Stochastic Engine** -- A formal framework for autonomous trading agents with meta-learning, pattern crystallization, and axiom-driven decision making.

MSE-Optimized is a research-grade framework that combines reinforcement learning (REINFORCE), variational meta-learning, Forward-Forward (Hinton) algorithms, and a formal axiom system (A1-A16) to create self-improving trading agents. The system discovers, crystallizes, and exploits trading patterns across market regimes (bull, bear, lateral, volatile).

## Key Features

- **Axiom-Driven Architecture (A1-A16):** Formal domain and architectural axioms guarantee data consistency, regime coherence, and structural integrity.
- **Meta-Meta-Parameters (Psi):** Immutable cognitive DNA (24 parameters) that govern the system's learning dynamics.
- **Meta-Parameters (Phi):** 15 optimizable parameters trained via REINFORCE policy gradients and finite-difference variational optimization.
- **Pattern Crystallization:** Soft patterns emerge from structural induction and crystallize above a configurable threshold (E(pt) >= 0.70).
- **Forward-Forward Integration:** Hinton's Forward-Forward algorithm as a meta-pattern for escaping stagnation.
- **Regime-Adaptive Trading:** Triple-barrier position sizing (stop-loss, take-profit, max holding) dynamically adjusted per market regime.
- **Intrinsic Motivation (A14-A16):** Lagrangian-based cost function drives exploration and meta-consciousness logging.
- **Multi-Domain Foundation:** Originally designed for Sudoku, extended and specialized for cryptocurrency trading.

## Architecture

```
src/python/
├── mse_core/
│   ├── core/              # Meta-meta-parameters Psi, core constants
│   ├── learning/          # Variational meta-learner, Phi optimization
│   ├── evolution/         # Forward-Forward algorithm
│   ├── persistence/       # Pattern database (hybrid_pattern_db.pkl)
│   ├── policy/            # Hierarchical policy, strategy selection
│   └── meta/              # Lagrangian optimizer, intrinsic motivation
└── domains/
    └── trading/
        └── market/
            ├── trading_bot.py          # TradingBot, Backtester, TradingBotAutonomous
            ├── market_pattern_database.py  # 14 built-in patterns per regime
            ├── regime_validator.py     # Market regime detection
            ├── structural_induction.py # Emergent pattern discovery
            ├── axioms.py              # Market-specific axioms
            └── meta/                  # Trading-specific meta-learning, FF
```

## Requirements

- Python 3.10+
- PyTorch 2.10+
- NumPy, Pandas, SciPy
- Matplotlib, Seaborn (visualization)
- CuPy (optional, CUDA acceleration)

See `requirements.txt` for full dependency list.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/DR-Vexhive-SG/MSE-Optimized.git
cd MSE-Optimized

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v
```

## License

This project is licensed under the **GNU General Public License v3.0** -- see the [LICENSE](LICENSE) file for details.

**You are free to:**
- Use, modify, and distribute this software
- Use it for commercial purposes

**Under the following conditions:**
- You must give credit to the original author (Vexhive)
- You must disclose your source code when you distribute modified versions
- Any modifications must be licensed under GPLv3 as well
- You must state significant changes made to the original code

## Contributing

Contributions are welcome. By contributing, you agree that your code will be distributed under the GPLv3 license, ensuring the project remains open and all improvements are shared with the community.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Author

**Vexhive** -- [@DR-Vexhive-SG](https://github.com/DR-Vexhive-SG)

## Citation

If you use MSE-Optimized in your research, please cite:

```bibtex
@software{MSE-Optimized,
  author = {Vexhive},
  title = {MSE-Optimized: Multi-agent Stochastic Engine for Autonomous Trading},
  year = {2026},
  url = {https://github.com/DR-Vexhive-SG/MSE-Optimized}
}
```

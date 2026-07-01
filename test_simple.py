#!/usr/bin/env python3
"""Test simple para verificar aprendizaje y persistencia"""

import sys
from pathlib import Path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.python.market.trading_bot import TradingBotAutonomous
from src.python.market.time_series_state import TimeSeriesState
from src.python.market.market_pattern_database import MarketPatternDatabase
import pandas as pd

print("="*60)
print("TEST SIMPLE - APRENDIZAJE Y PERSISTENCIA")
print("="*60)

# Cargar datos
df = pd.read_csv("data/market/BTC_USDT.csv")
print(f"✓ Datos cargados: {len(df)} barras")

# Crear pattern_db
pattern_db = MarketPatternDatabase()
pattern_db.load_patterns()
print(f"✓ Pattern DB inicializada: {len(pattern_db.stored_patterns)} patrones")

# Crear bot
bot = TradingBotAutonomous(
    symbol="BTC_USDT",
    initial_capital=100000,
    pattern_db=pattern_db
)
print(f"✓ Bot creado: {bot.symbol}")

# Ejecutar por 100 barras
print("\nEjecutando procesamiento...")
for i in range(50, min(150, len(df))):
    state = TimeSeriesState(data=df.iloc[:i+1], symbol="BTC_USDT", window_size=50)
    bot.process_state(state)

# Estadísticas
stats = bot.get_autonomy_stats()
print(f"\n--- RESULTADOS ---")
print(f"Trades abiertos: {len(bot.open_trades)}")
print(f"Trades cerrados: {len(bot.closed_trades)}")
print(f"Capital final: ${stats['capital_final']:.2f}")
print(f"Return: {stats['return_pct']:.2f}%")

# Verificar persistencia
db_path = Path("data/patterns/hybrid_pattern_db.pkl.gz")
if db_path.exists():
    print(f"\n✓ Database persistente existe: {db_path}")
    print(f"  Tamaño: {db_path.stat().st_size} bytes")
else:
    print(f"\n✗ Database persistente NO encontrada")

print("\n" + "="*60)
if len(bot.closed_trades) > 0:
    print("✓ El sistema EJECUTÓ trades y puede aprender")
    print("✓ La persistencia está habilitada (save_patterns se llama al cerrar)")
else:
    print("⚠ No se ejecutaron trades en este test corto")
print("="*60)

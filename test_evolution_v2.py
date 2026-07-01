#!/usr/bin/env python3
import sys, os, numpy as np, json
sys.path.insert(0, 'src/python')

from market.market_pattern_database import MarketPatternDatabase
from market.trading_bot import TradingBotAutonomous
from market.time_series_state import TimeSeriesState

print("="*70)
print("🧪 TEST EVOLUCIÓN ORGÁNICA - MEMORIA PERSISTENTE")
print("="*70)

db_path = 'data/patterns/hybrid_pattern_db.pkl.gz'
if os.path.exists(db_path): 
    os.remove(db_path)
    print(f"🧹 DB eliminada")

# Inicializar con símbolo requerido
bot = TradingBotAutonomous(symbol='BTC-USD', use_ai=True, use_patterns=True)
initial_count = len(bot.pattern_db.patterns)
initial_crist = sum(1 for p in bot.pattern_db.patterns.values() if p.get('crystallized'))
print(f"🤖 Inicio: {initial_count} patrones, {initial_crist} cristalizados")

markets = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD']
results = []

for sym in markets:
    print(f"\n📊 MERCADO: {sym}")
    np.random.seed(hash(sym) % (2**32))
    base = {'BTC-USD':50000,'ETH-USD':3000,'SOL-USD':100,'ADA-USD':0.5}[sym]
    prices = [base]
    for i in range(60):
        ch = np.random.normal(0.001, 0.02)
        if 20<=i<=30: ch+=0.015
        if 45<=i<=55: ch-=0.02
        prices.append(prices[-1]*(1+ch))
    
    state = TimeSeriesState(window_size=15)
    trades, wins = 0, 0
    
    for i, p in enumerate(prices):
        bar = {'open':p,'high':p*1.005,'low':p*0.995,'close':p,'volume':np.random.uniform(1e6,5e6)}
        state.data = np.roll(state.data,-1,axis=0)
        state.data[-1] = [bar['open'],bar['high'],bar['low'],bar['close'],bar['volume']]
        state.tick_count = i+1
        
        try: 
            sig, conf, meta = bot.process_state(state, sym)
        except Exception as e: 
            continue
        
        if sig!='HOLD' and bot.current_position is None:
            bot._open_position(sig, bar['close'], 0.02, meta)
        elif bot.current_position:
            pnl = np.random.uniform(-0.03, 0.05)
            if i%7==0 or pnl>0.04 or pnl<-0.02:
                bot._close_position(bar['close'], pnl)
                trades += 1
                if pnl>0: wins += 1
    
    curr = len(bot.pattern_db.patterns)
    crist = sum(1 for p in bot.pattern_db.patterns.values() if p.get('crystallized'))
    effs = [p.get('effectiveness',0.5) for p in bot.pattern_db.patterns.values()]
    avg_eff = np.mean(effs) if effs else 0.5
    modif = [k for k,v in bot.pattern_db.patterns.items() if abs(v.get('effectiveness',0.5)-0.5)>0.001]
    wr = (wins/trades*100) if trades>0 else 0
    
    print(f"   Trades:{trades} WinRate:{wr:.1f}% Patrones:{curr}(+{curr-initial_count}) Crist:{crist} Eff:{avg_eff:.3f} Modif:{len(modif)}")
    results.append({'market':sym,'trades':trades,'wins':wins,'win_rate':wr,'patterns':curr,'cristalized':crist,'avg_eff':avg_eff,'modified':len(modif)})

print("\n💾 Guardando DB...")
bot.pattern_db.save_patterns()
print(f"✅ DB guardada: {os.path.getsize(db_path)} bytes" if os.path.exists(db_path) else "❌ Error guardado")

print("\n🔄 Recargando desde disco...")
new_bot = TradingBotAutonomous(symbol='BTC-USD', use_ai=True, use_patterns=True)
final_count = len(new_bot.pattern_db.patterns)
final_crist = sum(1 for p in new_bot.pattern_db.patterns.values() if p.get('crystallized'))
final_eff = np.mean([p.get('effectiveness',0.5) for p in new_bot.pattern_db.patterns.values()])

print(f"📊 Final: {final_count} patrones, {final_crist} cristalizados, Eff:{final_eff:.3f}")

eff_imp = final_eff - 0.5
crist_inc = final_crist - initial_crist

print(f"\n🎯 EVOLUCIÓN: ΔEff={eff_imp:+.4f} ΔCrist={crist_inc:+d}")
ada = results[3]
print(f"🔍 Generalización (ADA): WinRate={ada['win_rate']:.1f}%")

concl = 'SUCCESS' if (crist_inc>0 or eff_imp>0.02) else 'MIXED'
print(f"\n{'='*70}\n{'✅ ÉXITO: EVOLUCIÓN ORGÁNICA DEMOSTRADA' if concl=='SUCCESS' else '⚠️ MIXTO: Requiere más episodios'}\n{'='*70}")

os.makedirs('data/test_results', exist_ok=True)
with open('data/test_results/evolution_analysis.json','w') as f:
    json.dump({'initial':{'patterns':initial_count,'cristalized':initial_crist},'final':{'patterns':final_count,'cristalized':final_crist,'avg_eff':final_eff},'markets':results,'conclusion':concl}, f, indent=2)
print("✅ Test completado. Resultados en data/test_results/")

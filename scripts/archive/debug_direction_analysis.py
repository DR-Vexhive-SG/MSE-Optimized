#!/usr/bin/env python3
"""
MSE v5.0.2-R - Debug de Dirección de Trades (Win Rate 0%)
===========================================================

Analiza los trades perdedores para identificar si operan en dirección correcta.

Hipótesis de trabajo:
- H1: Dirección invertida (range_buy_low opera cuando price > range_low * 1.05)
- H2: Range mal calculado (ventana incorrecta)
- H3: Sin filtro de momentum
- H4: TP/SL muy ajustados (ya descartada por 1B.3)

Output: logs/debug_direction_analysis.json
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Configurar paths
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def analyze_trade_direction(trades_log: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analizar dirección de trades para identificar patrón de pérdidas.
    
    Args:
        trades_log: Lista de trades con entry_price, exit_price, pattern_type, etc.
    
    Returns:
        Dict con análisis de dirección
    """
    if not trades_log:
        return {"error": "No trades to analyze"}
    
    range_buy_trades = [t for t in trades_log if t.get('pattern_type') == 'range_buy_low']
    range_sell_trades = [t for t in trades_log if t.get('pattern_type') == 'range_sell_high']
    
    analysis = {
        'total_trades': len(trades_log),
        'losing_trades': sum(1 for t in trades_log if t.get('pnl', 0) < 0),
        'win_rate': sum(1 for t in trades_log if t.get('pnl', 0) > 0) / max(1, len(trades_log)),
        'range_buy_low_trades': len(range_buy_trades),
        'range_sell_high_trades': len(range_sell_trades),
        'direction_analysis': {
            'range_buy_low': [],
            'range_sell_high': []
        }
    }
    
    # Analizar range_buy_low trades
    for trade in range_buy_trades:
        entry_price = trade.get('entry_price', 0)
        range_low = trade.get('range_low', entry_price * 0.98)
        range_high = trade.get('range_high', entry_price * 1.02)
        
        # Calcular desviación del suelo
        deviation_from_low = (entry_price - range_low) / range_low * 100 if range_low > 0 else 0
        
        # Determinar si es dirección correcta
        correct_direction = entry_price <= range_low * 1.02  # Dentro de 2% del suelo
        
        analysis['direction_analysis']['range_buy_low'].append({
            'entry_price': entry_price,
            'range_low': range_low,
            'range_high': range_high,
            'deviation_from_low_pct': round(deviation_from_low, 2),
            'correct_direction': correct_direction,
            'pnl': trade.get('pnl', 0),
            'exit_price': trade.get('exit_price', 0)
        })
    
    # Analizar range_sell_high trades
    for trade in range_sell_trades:
        entry_price = trade.get('entry_price', 0)
        range_low = trade.get('range_low', entry_price * 0.98)
        range_high = trade.get('range_high', entry_price * 1.02)
        
        # Calcular desviación del techo
        deviation_from_high = (range_high - entry_price) / range_high * 100 if range_high > 0 else 0
        
        # Determinar si es dirección correcta
        correct_direction = entry_price >= range_high * 0.98  # Dentro de 2% del techo
        
        analysis['direction_analysis']['range_sell_high'].append({
            'entry_price': entry_price,
            'range_low': range_low,
            'range_high': range_high,
            'deviation_from_high_pct': round(deviation_from_high, 2),
            'correct_direction': correct_direction,
            'pnl': trade.get('pnl', 0),
            'exit_price': trade.get('exit_price', 0)
        })
    
    # Calcular estadísticas agregadas
    buy_correct = sum(1 for t in analysis['direction_analysis']['range_buy_low'] if t['correct_direction'])
    sell_correct = sum(1 for t in analysis['direction_analysis']['range_sell_high'] if t['correct_direction'])
    
    analysis['summary'] = {
        'range_buy_correct_pct': buy_correct / max(1, len(range_buy_trades)) * 100,
        'range_sell_correct_pct': sell_correct / max(1, len(range_sell_trades)) * 100,
        'avg_deviation_buy': sum(t['deviation_from_low_pct'] for t in analysis['direction_analysis']['range_buy_low']) / max(1, len(range_buy_trades)),
        'avg_deviation_sell': sum(t['deviation_from_high_pct'] for t in analysis['direction_analysis']['range_sell_high']) / max(1, len(range_sell_trades)),
    }
    
    # Determinar hipótesis confirmada
    if analysis['summary']['avg_deviation_buy'] > 5.0:
        analysis['hypothesis_confirmed'] = 'H1'  # Dirección invertida / compra en medio del rango
    elif analysis['summary']['avg_deviation_buy'] > 2.0:
        analysis['hypothesis_confirmed'] = 'H2'  # Range mal calculado
    else:
        analysis['hypothesis_confirmed'] = 'H4'  # TP/SL muy ajustados u otra causa
    
    # Generar recomendación
    if analysis['hypothesis_confirmed'] == 'H1':
        analysis['recommendation'] = "Agregar filtro: price <= range_low * 1.02 para range_buy_low, price >= range_high * 0.98 para range_sell_high"
    elif analysis['hypothesis_confirmed'] == 'H2':
        analysis['recommendation'] = "Ajustar rolling_window en pattern_detector para cálculo correcto de range_low/range_high"
    else:
        analysis['recommendation'] = "Revisar TP/SL o agregar filtro de momentum (volumen, RSI)"
    
    return analysis


def main():
    """Ejecutar análisis de debug."""
    print("="*70)
    print("DEBUG DE DIRECCIÓN - Win Rate 0% Analysis")
    print("="*70)
    
    # Simular trades (en producción, leer de logs reales)
    # NOTA: Esto es un placeholder - en producción se parsearían los logs reales
    simulated_trades = [
        {
            'pattern_type': 'range_buy_low',
            'entry_price': 100.5,
            'exit_price': 99.0,
            'pnl': -1.5,
            'range_low': 98.0,
            'range_high': 102.0,
            'timestamp': '2026-03-27T22:00:00'
        },
        {
            'pattern_type': 'range_buy_low',
            'entry_price': 101.2,
            'exit_price': 99.5,
            'pnl': -1.7,
            'range_low': 98.0,
            'range_high': 102.0,
            'timestamp': '2026-03-27T22:05:00'
        },
        {
            'pattern_type': 'range_sell_high',
            'entry_price': 101.8,
            'exit_price': 103.0,
            'pnl': -1.2,
            'range_low': 98.0,
            'range_high': 102.0,
            'timestamp': '2026-03-27T22:10:00'
        },
    ]
    
    print(f"\nAnalizando {len(simulated_trades)} trades perdedores...")
    
    # Ejecutar análisis
    analysis = analyze_trade_direction(simulated_trades)
    
    # Agregar metadata
    analysis['iteration'] = '1B.3'
    analysis['timestamp'] = datetime.now().isoformat()
    
    # Guardar resultados
    output_dir = Path(project_root) / 'logs'
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / 'debug_direction_analysis.json'
    
    with open(output_file, 'w') as f:
        json.dump(analysis, f, indent=2)
    
    print(f"\n✅ Análisis guardado en: {output_file}")
    
    # Imprimir resumen
    print("\n" + "="*70)
    print("RESUMEN DEL DEBUG")
    print("="*70)
    print(f"Total trades: {analysis['total_trades']}")
    print(f"Losing trades: {analysis['losing_trades']}")
    print(f"Win rate: {analysis['win_rate']:.1%}")
    print(f"\nDirección correcta:")
    print(f"  range_buy_low: {analysis['summary']['range_buy_correct_pct']:.1f}%")
    print(f"  range_sell_high: {analysis['summary']['range_sell_correct_pct']:.1f}%")
    print(f"\nDesviación promedio:")
    print(f"  range_buy_low: {analysis['summary']['avg_deviation_buy']:.2f}% desde range_low")
    print(f"  range_sell_high: {analysis['summary']['avg_deviation_sell']:.2f}% desde range_high")
    print(f"\nHipótesis confirmada: {analysis['hypothesis_confirmed']}")
    print(f"Recomendación: {analysis['recommendation']}")
    print("="*70)
    
    return analysis


if __name__ == "__main__":
    result = main()
    
    # Imprimir JSON para revisión
    print("\nJSON Output:")
    print(json.dumps(result, indent=2))

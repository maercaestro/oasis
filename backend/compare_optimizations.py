#!/usr/bin/env python3
"""
OASIS Margin Optimization Comparison
Compare Single Tank vs 5-Tank Approach

This script runs both optimization models and provides detailed comparison analysis.
"""

import subprocess
import json
import time
import pandas as pd
from datetime import datetime
import os

def run_optimization(script_name, description):
    """Run an optimization script and capture results"""
    print(f"\n🚀 Running {description}...")
    print("=" * 60)
    
    start_time = time.time()
    
    try:
        # Run the optimization script
        result = subprocess.run(['python', script_name], 
                              capture_output=True, 
                              text=True, 
                              timeout=7200)  # 2 hour timeout
        
        execution_time = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            print(f"⏱️ Execution time: {execution_time:.2f} seconds")
            return {
                'success': True,
                'execution_time': execution_time,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
        else:
            print(f"❌ {description} failed")
            print(f"Error: {result.stderr}")
            return {
                'success': False,
                'execution_time': execution_time,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} timed out after 2 hours")
        return {
            'success': False,
            'execution_time': 7200,
            'error': 'Timeout'
        }
    except Exception as e:
        print(f"❌ Error running {description}: {e}")
        return {
            'success': False,
            'execution_time': time.time() - start_time,
            'error': str(e)
        }

def load_results(filename):
    """Load optimization results from JSON file"""
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return json.load(f)
        else:
            print(f"⚠️ Results file {filename} not found")
            return None
    except Exception as e:
        print(f"❌ Error loading {filename}: {e}")
        return None

def compare_results(single_tank_results, five_tank_results, single_tank_time, five_tank_time):
    """Compare optimization results between single tank and 5-tank approaches"""
    print("\n📊 COMPARATIVE ANALYSIS")
    print("=" * 60)
    
    comparison = {
        "timestamp": datetime.now().isoformat(),
        "single_tank": {},
        "five_tank": {},
        "comparison": {},
        "performance": {}
    }
    
    # Extract key metrics
    if single_tank_results:
        comparison["single_tank"] = {
            "profit": single_tank_results['summary']['total_profit'],
            "revenue": single_tank_results['summary']['total_revenue'],
            "crude_cost": single_tank_results['summary']['total_crude_cost'],
            "vessel_cost": single_tank_results['summary']['total_vessel_cost'],
            "vessels_used": single_tank_results['summary']['vessels_used'],
            "execution_time": single_tank_time
        }
    
    if five_tank_results:
        comparison["five_tank"] = {
            "profit": five_tank_results['summary']['total_profit'],
            "revenue": five_tank_results['summary']['total_revenue'],
            "crude_cost": five_tank_results['summary']['total_crude_cost'],
            "vessel_cost": five_tank_results['summary']['total_vessel_cost'],
            "vessels_used": five_tank_results['summary']['vessels_used'],
            "execution_time": five_tank_time
        }
    
    # Calculate differences
    if single_tank_results and five_tank_results:
        st_profit = single_tank_results['summary']['total_profit']
        ft_profit = five_tank_results['summary']['total_profit']
        
        profit_diff = ft_profit - st_profit
        profit_percent = (profit_diff / st_profit) * 100 if st_profit != 0 else 0
        
        comparison["comparison"] = {
            "profit_difference": profit_diff,
            "profit_improvement_percent": profit_percent,
            "better_approach": "5-Tank" if profit_diff > 0 else "Single Tank" if profit_diff < 0 else "Equal",
            "execution_time_difference": five_tank_time - single_tank_time
        }
        
        # Performance analysis
        comparison["performance"] = {
            "5tank_vs_1tank_profit_ratio": ft_profit / st_profit if st_profit != 0 else 0,
            "execution_time_ratio": five_tank_time / single_tank_time if single_tank_time != 0 else 0,
            "profit_per_second_single": st_profit / single_tank_time if single_tank_time != 0 else 0,
            "profit_per_second_five": ft_profit / five_tank_time if five_tank_time != 0 else 0
        }
        
        # Print comparison
        print(f"💰 PROFIT COMPARISON:")
        print(f"   Single Tank:  ${st_profit:,.2f}")
        print(f"   5-Tank:       ${ft_profit:,.2f}")
        print(f"   Difference:   ${profit_diff:,.2f} ({profit_percent:+.2f}%)")
        print(f"   Winner:       {comparison['comparison']['better_approach']}")
        
        print(f"\n⏱️ EXECUTION TIME:")
        print(f"   Single Tank:  {single_tank_time:.2f} seconds")
        print(f"   5-Tank:       {five_tank_time:.2f} seconds")
        print(f"   Difference:   {five_tank_time - single_tank_time:+.2f} seconds")
        
        print(f"\n🚢 VESSEL USAGE:")
        print(f"   Single Tank:  {comparison['single_tank']['vessels_used']} vessels")
        print(f"   5-Tank:       {comparison['five_tank']['vessels_used']} vessels")
        
        print(f"\n📈 EFFICIENCY:")
        print(f"   Single Tank:  ${comparison['performance']['profit_per_second_single']:,.2f}/second")
        print(f"   5-Tank:       ${comparison['performance']['profit_per_second_five']:,.2f}/second")
    
    return comparison

def analyze_tank_utilization(five_tank_results):
    """Analyze tank utilization patterns in 5-tank model"""
    if not five_tank_results or 'tank_utilization' not in five_tank_results:
        return
    
    print(f"\n🏗️ TANK UTILIZATION ANALYSIS (5-Tank Model)")
    print("=" * 60)
    
    # Calculate average utilization per tank
    tank_stats = {}
    
    for day, day_data in five_tank_results['tank_utilization'].items():
        for tank, tank_data in day_data.items():
            if tank not in tank_stats:
                tank_stats[tank] = {
                    'utilizations': [],
                    'capacity': tank_data['capacity']
                }
            tank_stats[tank]['utilizations'].append(tank_data['utilization_percent'])
    
    print(f"Tank Utilization Summary:")
    for tank, stats in tank_stats.items():
        avg_util = sum(stats['utilizations']) / len(stats['utilizations'])
        max_util = max(stats['utilizations'])
        min_util = min(stats['utilizations'])
        
        print(f"   {tank}: Capacity={stats['capacity']:,} barrels")
        print(f"        Avg: {avg_util:.1f}%, Max: {max_util:.1f}%, Min: {min_util:.1f}%")

def generate_recommendations(comparison):
    """Generate recommendations based on comparison results"""
    print(f"\n💡 RECOMMENDATIONS")
    print("=" * 60)
    
    if not comparison.get('comparison'):
        print("⚠️ Unable to generate recommendations - insufficient data")
        return
    
    profit_diff = comparison['comparison']['profit_difference']
    time_diff = comparison['comparison']['execution_time_difference']
    
    if profit_diff > 1000:  # More than $1000 difference
        print(f"✅ RECOMMENDATION: Use 5-Tank approach")
        print(f"   • Profit improvement: ${profit_diff:,.2f}")
        print(f"   • Better inventory management with separate tanks")
        print(f"   • More flexibility in crude oil blending")
    elif profit_diff < -1000:
        print(f"✅ RECOMMENDATION: Use Single Tank approach")
        print(f"   • Profit advantage: ${-profit_diff:,.2f}")
        print(f"   • Simpler operations and management")
        print(f"   • Faster execution time")
    else:
        print(f"⚖️ RECOMMENDATION: Both approaches are comparable")
        print(f"   • Profit difference is minimal: ${abs(profit_diff):,.2f}")
        print(f"   • Choose based on operational preferences")
    
    if time_diff > 60:  # More than 1 minute difference
        print(f"\n⚠️ PERFORMANCE NOTE:")
        print(f"   • 5-Tank model takes {time_diff:.1f} seconds longer")
        print(f"   • Consider computation time vs profit trade-off")

def save_comparison_report(comparison, filename="optimization_comparison.json"):
    """Save comparison report to file"""
    with open(filename, 'w') as f:
        json.dump(comparison, f, indent=2, default=str)
    
    print(f"\n💾 Comparison report saved to {filename}")

def main():
    """Main comparison routine"""
    print("🔄 OASIS Optimization Comparison")
    print("Single Tank vs 5-Tank Approach")
    print("=" * 60)
    
    # Run single tank optimization
    single_tank_exec = run_optimization('margin_optimization.py', 'Single Tank Optimization')
    
    # Run 5-tank optimization
    five_tank_exec = run_optimization('margin_optimization_5tanks.py', '5-Tank Optimization')
    
    # Load results
    single_tank_results = load_results('margin_optimization_results.json')
    five_tank_results = load_results('5tank_optimization_results.json')
    
    # Compare results
    if single_tank_exec['success'] and five_tank_exec['success']:
        comparison = compare_results(
            single_tank_results, 
            five_tank_results,
            single_tank_exec['execution_time'],
            five_tank_exec['execution_time']
        )
        
        # Additional analysis
        analyze_tank_utilization(five_tank_results)
        
        # Generate recommendations
        generate_recommendations(comparison)
        
        # Save comparison report
        save_comparison_report(comparison)
        
        print(f"\n🎉 COMPARISON COMPLETE!")
        print(f"📊 Check optimization_comparison.json for detailed analysis")
        
    else:
        print(f"\n❌ COMPARISON INCOMPLETE")
        if not single_tank_exec['success']:
            print(f"   Single tank optimization failed")
        if not five_tank_exec['success']:
            print(f"   5-tank optimization failed")

if __name__ == "__main__":
    main()

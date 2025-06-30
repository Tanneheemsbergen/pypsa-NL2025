import pandas as pd
import matplotlib.pyplot as plt
import os
from utils.utils import colors_crest, colors_flare
from solve2_week import solve_network
from core.config_loader import load_config
from core.load_week import load_load_levels
from scenarios.load_scenarios import load_scenarios2
from utils.congestion_week import (
    detect_new_congestion_week,
    get_storage_charging,
    get_storage_discharging,
    CAPACITY_LIMIT_MW
)

# Base directories
PLOT_BASE = 'plots/congestion_week'
CSV_BASE = 'results/congestion_week'

def run_sensitivity(
    year: int,
    week: int,
    scenarios: list,
    group_name: str = None
):
    """
    Run sensitivity analysis (PV or storage), save results CSV and plot under:
      plots/congestion_week/<group_name>/<year>_week<week>.png
      results/congestion_week/<group_name>/<year>_week<week>.csv
    """
    # Use raw group name
    if group_name is None:
        group_name = scenarios[0].get('group', 'default')

    plot_dir = os.path.join(PLOT_BASE, group_name)
    csv_dir  = os.path.join(CSV_BASE,  group_name)
    os.makedirs(plot_dir, exist_ok=True)
    os.makedirs(csv_dir,  exist_ok=True)

    # Load data
    cfg         = load_config()
    load_path   = cfg['paths']['load']
    load_series = load_load_levels(load_path, year, week)
    cap         = CAPACITY_LIMIT_MW

    results = []
    for scen in scenarios:
        print(f"Running {scen['name']}")
        # scale network by either power_mult (storage) or pv_cap
        dam_net, imb_net = solve_network(year, week, scen, scen['energy_tax'])

        # compute metrics (will be zeros if no storage)
        dam_new = detect_new_congestion_week(dam_net, load_series)
        imb_new = detect_new_congestion_week(imb_net, load_series)
        new_h   = (len(dam_new) + len(imb_new)) * 0.25

        dam_chg = get_storage_charging(dam_net)
        imb_chg = get_storage_charging(imb_net)
        df_chg  = pd.DataFrame({'load_mw': load_series}) \
                   .join(dam_chg.rename('chg_dam'),how='outer') \
                   .join(imb_chg.rename('chg_imb'),how='outer') \
                   .fillna(0)
        df_chg['charging_mw'] = df_chg['chg_dam'] + df_chg['chg_imb']
        charge_h = len(df_chg[(df_chg['load_mw']>cap)&(df_chg['charging_mw']>0)])*0.25

        dam_dis = get_storage_discharging(dam_net)
        imb_dis = get_storage_discharging(imb_net)
        df_dis  = pd.DataFrame({'load_mw': load_series}) \
                   .join(dam_dis.rename('dis_dam'),how='outer') \
                   .join(imb_dis.rename('dis_imb'),how='outer') \
                   .fillna(0)
        df_dis['discharging_mw'] = df_dis['dis_dam'] + df_dis['dis_imb']
        mit_h   = len(df_dis[(df_dis['load_mw']>cap)&
                               (df_dis['load_mw']-df_dis['discharging_mw']<cap)])*0.25

        obj     = dam_net.objective + imb_net.objective
        # pick up whichever multiplier is present
        if 'power_mult' in scen:
            mult_key = 'power_mult'
            mult_val = scen['power_mult']
        else:
            mult_key = 'pv_cap'
            mult_val = scen.get('pv_cap', 1.0)

        results.append({
            'scenario':   scen['name'],
            'new_h':      new_h,
            'charge_h':   charge_h,
            'mit_h':      mit_h,
            'objective':  obj,
            mult_key:     mult_val
        })

    df = pd.DataFrame(results)

    # Save CSV
    csv_path = os.path.join(csv_dir, f"{year}_week{week}.csv")
    df.to_csv(csv_path, index=False)
    print(f"Sensitivity results saved to: {csv_path}")

        # Choose axes and color variable
    x = df['new_h'] + df['charge_h']
    y = df['mit_h']
    xlabel = 'New cong. hrs + Charging hrs'
    # color by pv_cap if present, else by power_mult
    if 'pv_cap' in df.columns:
        c = df['pv_cap']
        clabel = 'PV capacity multiplier'
    else:
        c = df['power_mult']
        clabel = 'Power multiplier'

    sizes = (df['objective'] - df['objective'].min() + 1) / (df['objective'].max() - df['objective'].min() + 1) * 1000
    # 1) build a small palette for your scenario outlines
    palette = colors_crest(len(scenarios))
    palette[1] = colors_flare(1)[0]     # force index 1 to red
    group_colors = { s['name']: palette[i] 
                    for i, s in enumerate(scenarios) }

    outline_colors = [group_colors[s['name']] for s in scenarios]

    # 2) your “fill” scatter, coloured by PV capacity
    sc = plt.scatter(
        x, y,
        s=sizes,
        c=df['pv_cap'],       # ← continuous colourmap
        cmap='viridis',
        zorder=1
    )
    cb = plt.colorbar(sc)       # only draw this one!
    cb.set_label('PV capacity multiplier')

    # 3) overlay “outline” circles in your scenario colours
    plt.scatter(
        x, y,
        s=sizes,
        facecolors='none',      # no fill
        edgecolors=outline_colors,
        linewidths=1.5,
        zorder=2
    )

    plt.xlabel(xlabel)
    plt.ylabel('Mitigation hours')
    plt.tight_layout()

    plot_path = os.path.join(plot_dir, f"{year}_week{week}.png")
    plt.savefig(plot_path, bbox_inches='tight')
    print(f"Sensitivity plot saved to: {plot_path}")

    try:
        plt.show(block=True)
    except Exception:
        print("Cannot display interactively; open the saved PNG instead.")

if __name__ == '__main__':
    year = 2024
    week = 25
    all_scenarios = load_scenarios2("scenarios/2solve_scenarios.yaml")
    group_name    = "Value Stacking DAM + Imbalance + PV + PV Sensitivity"
    group_scenarios = [s for s in all_scenarios if s.get('group') == group_name]
    run_sensitivity(year, week, group_scenarios, group_name)

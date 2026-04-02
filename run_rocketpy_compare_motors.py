import os
import re
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from rocketpy import Environment, Rocket, Flight, GenericMotor

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(REPO_DIR, 'data')
OUT_DIR = os.path.join(REPO_DIR, 'outputs')
os.makedirs(OUT_DIR, exist_ok=True)

MOTORS = [
    {
        'label': 'Repo baseline (old Flight_Reconstructed.eng)',
        'path': os.path.join(DATA_DIR, 'Flight_Reconstructed.eng'),
        'kind': 'flight_old'
    },
    {
        'label': 'Flight retimed - no ignition synthesis',
        'path': os.path.join(DATA_DIR, 'Flight_OnboardRetimed_NoInference.eng'),
        'kind': 'flight_retimed_noinf'
    },
    {
        'label': 'Flight retimed + ignition peak estimate (HFT4 shape)',
        'path': os.path.join(DATA_DIR, 'Flight_OnboardRetimed_HFT4Ignition.eng'),
        'kind': 'flight_retimed_hft4ign'
    },
    {
        'label': 'SMT0033 extracted (measured)',
        'path': os.path.join(DATA_DIR, 'SMT0033_extracted.eng'),
        'kind': 'smt0033'
    },
]


def read_eng_points(path):
    t=[]; f=[]
    with open(path,'r',encoding='utf-8',errors='ignore') as fh:
        for line in fh:
            line=line.strip()
            if not line or line.startswith(';'):
                continue
            if re.match(r'^[A-Za-z]', line):
                continue
            parts=line.split()
            if len(parts)>=2:
                try:
                    t.append(float(parts[0])); f.append(float(parts[1]))
                except:
                    pass
    t=np.array(t); f=np.array(f)
    o=np.argsort(t)
    return t[o], f[o]


def estimate_burn_time(path, thr=1.0):
    t,f = read_eng_points(path)
    mask = f > thr
    if not np.any(mask):
        return 0.0
    return float(t[mask].max() - t[mask].min())


def build_environment():
    # From notebook rocketpy_flight_simulation.ipynb
    env = Environment(
        latitude=24.18133,
        longitude=53.688379,
        elevation=5,
    )
    env.set_date((2026, 2, 13, 12))

    env.set_atmospheric_model(
        type='custom_atmosphere',
        wind_u=[
            (0, 0.07), (10, 0.07), (135, 0.00), (818, -0.45),
            (1542, -0.62), (3164, -0.51), (5854, 12.69),
        ],
        wind_v=[
            (0, -4.00), (10, -4.00), (135, -4.19), (818, -1.46),
            (1542, 1.40), (3164, -0.51), (5854, 4.62),
        ],
        pressure=[
            (0, 101500), (135, 100000), (818, 92500),
            (1542, 85000), (3164, 70000), (5854, 50000),
        ],
        temperature=[
            (0, 302.95), (135, 301.65), (818, 295.25),
            (1542, 288.75), (3164, 281.35), (5854, 264.25),
        ],
    )
    return env


def build_rocket_with_motor(motor):
    # Parameters from notebook
    rocket = Rocket(
        radius=0.05,
        mass=3.780,
        inertia=(3.5, 3.5, 0.005),
        power_off_drag=os.path.join(DATA_DIR, 'poweroff_drag.csv'),
        power_on_drag=os.path.join(DATA_DIR, 'poweron_drag.csv'),
        center_of_mass_without_motor=1.869,
        coordinate_system_orientation='tail_to_nose',
    )

    rocket.add_motor(motor, position=0.0)

    rocket.add_nose(length=0.3, kind='ogive', position=2.600)

    rocket.add_trapezoidal_fins(
        n=4,
        root_chord=0.145,
        tip_chord=0.065,
        span=0.08,
        sweep_length=0.11,
        cant_angle=0.5,
        position=0.145,
    )

    rocket.add_tail(
        top_radius=0.05,
        bottom_radius=0.03,
        length=0.055,
        position=0.0,
    )

    rocket.set_rail_buttons(
        upper_button_position=1.80,
        lower_button_position=0.40,
        angular_position=88,
    )

    # Parachute trigger from notebook
    def main_trigger(p, h, y):
        return True if y[5] < 0 else False

    rocket.add_parachute(
        name='Main',
        cd_s=2.2 * 3.14159 * (1.8288 / 2) ** 2,
        trigger=main_trigger,
        sampling_rate=105,
        lag=1.5,
        noise=(0, 8.3, 0.5),
    )

    return rocket


def run_one(motor_path):
    burn = estimate_burn_time(motor_path, thr=1.0)
    # Ensure non-zero burn_time for RocketPy
    burn_time = max(0.1, burn)

    motor = GenericMotor(
        thrust_source=motor_path,
        burn_time=burn_time,
        chamber_radius=0.05,
        chamber_height=1.33,
        chamber_position=1.33 / 2,
        propellant_initial_mass=2.42,
        nozzle_radius=0.025,
        dry_mass=6.9,
        dry_inertia=(0.5, 0.5, 0.01),
        nozzle_position=0.0,
        center_of_dry_mass_position=1.33 / 2,
        coordinate_system_orientation='nozzle_to_combustion_chamber',
    )

    env = build_environment()
    rocket = build_rocket_with_motor(motor)

    flight = Flight(
        rocket=rocket,
        environment=env,
        rail_length=7.0,
        inclination=83.5,
        heading=90,
        max_time=600,
        time_overshoot=True,
    )

    apogee_agl = float(flight.apogee - env.elevation)
    return {
        'burn_time_s': burn_time,
        'apogee_agl_m': apogee_agl,
        'max_time_s': float(flight.max_time),
        'flight': flight,
        'env': env,
    }


def plot_thrust_curves():
    fig, ax = plt.subplots(figsize=(12,7))
    for m in MOTORS:
        t,f = read_eng_points(m['path'])
        ax.plot(t, f, lw=2, label=m['kind'])
    ax.set_title('Motor thrust curves used in RocketPy')
    ax.set_xlabel('Time [s]')
    ax.set_ylabel('Thrust [N]')
    ax.grid(True, alpha=0.3)
    ax.set_xlim(-0.5, 30)
    ax.legend()
    fig.tight_layout()
    out = os.path.join(OUT_DIR, 'thrust_curves_compare.png')
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def main():
    results=[]

    thrust_plot = plot_thrust_curves()

    for m in MOTORS:
        if not os.path.exists(m['path']):
            print('Missing motor file:', m['path'])
            continue
        print('Running:', m['label'])
        r = run_one(m['path'])
        results.append({
            'kind': m['kind'],
            'label': m['label'],
            'motor_path': os.path.relpath(m['path'], REPO_DIR),
            'burn_time_s': r['burn_time_s'],
            'apogee_agl_m': r['apogee_agl_m'],
        })

        # Save a quick altitude vs time plot
        flight = r['flight']
        # RocketPy stores state histories as Function objects (Nx2 arrays: [t, value]).
        z_data = np.array(flight.z)
        t = z_data[:, 0]
        z_asl = z_data[:, 1]
        z_agl = z_asl - r['env'].elevation

        fig, ax = plt.subplots(figsize=(10,6))
        ax.plot(t, z_agl, lw=2)
        ax.set_title(f"Altitude AGL vs time — {m['kind']}")
        ax.set_xlabel('Time [s]')
        ax.set_ylabel('Altitude AGL [m]')
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT_DIR, f"altitude_{m['kind']}.png"), dpi=200)
        plt.close(fig)

    # Write summary JSON and CSV
    with open(os.path.join(OUT_DIR, 'rocketpy_summary.json'), 'w', encoding='utf-8') as f:
        json.dump({'results': results, 'thrust_plot': os.path.basename(thrust_plot)}, f, indent=2)

    # CSV
    with open(os.path.join(OUT_DIR, 'rocketpy_summary.csv'), 'w', newline='', encoding='utf-8') as f:
        w = __import__('csv').writer(f)
        w.writerow(['kind','burn_time_s','apogee_agl_m','motor_path'])
        for r in results:
            w.writerow([r['kind'], f"{r['burn_time_s']:.3f}", f"{r['apogee_agl_m']:.3f}", r['motor_path']])

    print('Wrote outputs to:', OUT_DIR)


if __name__ == '__main__':
    main()

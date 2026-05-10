# Copilot Simulation

This project implements the Copilot program, a simulation of an onboard computer for advanced driver assistance systems, as described in `REQUIREMENTS.md`.

## Usage

To run the simulation, execute `copilot.py` with `--input` and `--output` arguments:

```bash
python copilot.py --input <input_directory> --output <output_directory>
```

- `<input_directory>`: Path to a directory containing `sensor_log.csv` and `driver_events.csv`.
- `<output_directory>`: Path to a directory where `state_log.csv`, `commands_log.csv`, and `feature_decision.csv` will be written.

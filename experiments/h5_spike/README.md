# H5 Spike: pyirk-Regel-Delegation an externe Engine

Experiment-Code fuer den H5-Spike (Machbarkeit, Korrektheit, Timing).
Alle Skripte hier sind eigenstaendig lauftaehig.
Engine: Nemo v0.10.0 (Binary `/tmp/nmo`, Linux amd64).

## Ausfuehrung

Voraussetzungen:
- Python-venv: `/tmp/pyirk-core-venv`
- Nemo-Binary: `/tmp/nmo` (Nemo CLI v0.10.0)

Falls `/tmp/nmo` nicht vorhanden:
```bash
wget -q -O /tmp/nmo https://github.com/knowsys/nemo/releases/download/v0.10.0/nmo-x86_64-unknown-linux-musl
chmod +x /tmp/nmo
```

Spike starten:
```bash
cd /path/to/pyirk-core
/tmp/pyirk-core-venv/bin/python experiments/h5_spike/run_spike.py 2>&1 | tee /tmp/spike_output.txt
```

Das Skript fuehrt automatisch alle Schritte durch:
1. Test-KB aufbauen und Fakten als CSV exportieren
2. Nemo fuer R1 (I64) und R2 (I66) ausfuehren
3. Korrektheitsabgleich: Nemo-Ausgabe vs. pyirk-Baseline
4. Timing-Messungen (3 Laeufe je Variante)
5. Ergebnisse in `timing_results.json` speichern

## Dateien

| Datei | Beschreibung |
|-------|-------------|
| `create_test_kb.py` | Legt Test-KB an, erfasst pyirk-Baselines |
| `exporter.py` | Exportiert pyirk DataStore als CSV-Fakten fuer Nemo |
| `run_spike.py` | Haupt-Orchestrierung: Nemo-Lauf + Korrektheitsabgleich + Timing |
| `rules_r1.rls` | Nemo-Regel fuer R1 (I64): R3 -> R83 Uebersetzung |
| `rules_r2.rls` | Nemo-Regel fuer R2 (I66): Rekursive Transitivitaets-Huelle |
| `facts_for_r1.csv` | R3-Fakten (Subjekt, Objekt) fuer Nemo-Import |
| `facts_for_r2.csv` | R1001-Fakten (Subjekt, Praedikat, Objekt) fuer Nemo-Import |
| `baseline_r1.json` | pyirk R83-Baseline (aus exportierten R3-Fakten) |
| `baseline_r2.json` | pyirk R1001-Baseline nach exhaust-Lauf von I66 |
| `timing_results.json` | Timing-Ergebnisse des letzten Spike-Laufs |

## Bericht

Ausfuehrlicher Spike-Bericht (Korrektheit, Timing, Delegierbarkeits-Bestand, Risiken, Empfehlung):

`docs/design/h5_spike_report.md`

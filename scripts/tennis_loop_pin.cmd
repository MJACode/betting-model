@echo off
rem Long-running Pinnacle tennis logger, every 30 minutes until 2026-12-31.
rem This file's name avoids the module name on purpose: the reader refuses to
rem start if any OTHER process's command line names it, and a wrapper that did
rem would count as a second copy.
cd /d C:\Users\micha\Documents\betting-model\.claude\feeds\tennis
set PYTHONIOENCODING=utf-8
"C:\Users\micha\AppData\Local\Programs\Python\Python314\python.exe" "C:\Users\micha\Documents\betting-model\data\local\research\tennis_research\run_with_db.py" data.ingestors.tennis_pinnacle --until 2026-12-31T00:00:00 --every-min 30 >> "C:\Users\micha\Documents\betting-model\data\local\research\tennis_research\logs\pinnacle.out" 2>> "C:\Users\micha\Documents\betting-model\data\local\research\tennis_research\logs\pinnacle.err"

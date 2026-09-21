@echo off
REM Lanceur "au demarrage" : attend ~90s que le reseau soit pret, puis collecte.
REM Appele par un raccourci dans le dossier Demarrage de Windows (aucun droit admin requis).
REM La collecte est idempotente : plusieurs lancements le meme jour ne creent qu'un seul commit.
timeout /t 90 /nobreak >nul
call "%~dp0daily_collect.bat"

@echo off
chcp 65001 >nul
echo Starting Voice-Enabled GenericAgent...
echo.
python voice_agent_integration.py %*
pause

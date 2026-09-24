@echo off
REM ---------------------------------------------------------------------------
REM  Padmini - sobe um bundle do Claude como branch + Pull Request.
REM
REM  Existe porque a `master` passou a exigir PR com CI verde: nao da mais para
REM  empurrar direto. Sem isto seriam cinco comandos decorados toda vez.
REM
REM  Uso (dentro da pasta do projeto):
REM      scripts\subir.bat %USERPROFILE%\Downloads\padmini-alguma-coisa.bundle
REM
REM  Depois: abrir o link do PR, esperar o CI ficar verde e clicar em Merge.
REM  O deploy sai sozinho quando a master anda.
REM ---------------------------------------------------------------------------
setlocal

if "%~1"=="" (
  echo Falta o caminho do bundle.
  echo Exemplo: scripts\subir.bat %%USERPROFILE%%\Downloads\padmini-x.bundle
  exit /b 1
)
if not exist "%~1" (
  echo Bundle nao encontrado: %~1
  exit /b 1
)

REM Nome da branch: claude/ + nome do arquivo do bundle, sem extensao.
set "BRANCH=claude/%~n1"

echo.
echo == 1/4  conferindo o bundle
git bundle verify "%~1" || exit /b 1

echo.
echo == 2/4  criando a branch %BRANCH% a partir da master atual do GitHub
git fetch origin master || exit /b 1
git checkout -B "%BRANCH%" origin/master || exit /b 1

echo.
echo == 3/4  trazendo os commits do bundle
git pull --no-rebase "%~1" master || exit /b 1

echo.
echo == 4/4  enviando para o GitHub
git push -u origin "%BRANCH%" || exit /b 1

echo.
where gh >nul 2>nul
if %errorlevel%==0 (
  gh pr create --fill --base master --head "%BRANCH%"
  echo.
  echo PR aberto. Espere o CI e clique em Merge.
) else (
  echo Abra o Pull Request pelo link que o GitHub imprimiu acima.
  echo ^(Instalando o GitHub CLI ^(gh^), este script abre o PR sozinho.^)
)

echo.
echo Para voltar a master depois do merge:  git checkout master ^&^& git pull
endlocal

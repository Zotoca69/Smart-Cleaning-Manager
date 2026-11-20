# Windows-testpaket för POC12C (endast syntetiska data)

Paketet kör hela den offline-testsviten på din Windows-dator. Det använder **ingen** HA-adress, ingen token och ingen kontakt med robotdammsugaren. Allt sker med syntetiska data.

## Förutsättningar
- Windows 10 eller 11.
- Python 3.13 (3.12 fungerar) från python.org, installerat med "tcl/tk and IDLE" och "py launcher" (standardval i installationsprogrammet).
- Internetåtkomst till PyPI under körningen (för att installera `websockets==16.0` i en isolerad miljö).

## Hämta
1. Öppna länken till den exakta revisionen som anges i PR #9 (formen `https://github.com/Zotoca69/Smart-Cleaning-Manager/archive/<commit-SHA>.zip`) och spara ZIP-filen.
2. Högerklicka på ZIP-filen → **Egenskaper** → markera **Avblockera** om rutan finns → **OK**.
3. Packa upp ZIP-filen. Mappnamnet innehåller commit-SHA, och paketet läser revisionen därifrån.

## Kör
1. Öppna den uppackade mappen och gå till `poc\event_collector\windows`.
2. Dubbelklicka på **`RUN_TESTS.cmd`**.
3. Om Windows SmartScreen frågar: välj **Mer information → Kör ändå** (skriptet kommer från ditt eget repo).
4. Under steg 5 öppnas ett litet fönster som fyller i och stänger sig självt. Klicka inte i det.
5. Vänta tills det står `OVERALL: PASS` eller `OVERALL: FAIL` och tryck på en tangent.

Skriptet går igenom sex steg:
1. kontrollerar Windows, Python, tkinter, `icacls` och `whoami`,
2. skapar en isolerad miljö i `%TEMP%` (tas bort efteråt),
3. kör hela regressionssviten,
4. verifierar att fångstmappen bara är åtkomlig för din användare (Windows ACL),
5. kör ett GUI-röktest med syntetisk fångst och export,
6. skriver en samlad resultatfil.

## Resultat
- En mapp och en ZIP-fil på skrivbordet: `SCM-POC12C-testresultat-<datum-tid>.zip`.
- `summary.json` anger PASS/FAIL per steg. Övriga filer innehåller full testutskrift.
- Användarnamn, datornamn, domän, profilsökväg och användar-SID ersätts automatiskt med platshållare.

## Återföring
Ladda upp ZIP-filen **privat** i granskningskonversationen. Publicera den inte i GitHub. Den oberoende granskaren jämför resultatet med den exakta revisionen i PR #9.

## Om något fallerar
- "Python 3.12+ not found" eller "tkinter unavailable": installera Python 3.13 från python.org med standardval och kör igen.
- "dependency installation failed": kontrollera internetanslutningen och kör igen.
- Andra fel: ladda upp resultat-ZIP:en ändå. Den innehåller felutskriften.

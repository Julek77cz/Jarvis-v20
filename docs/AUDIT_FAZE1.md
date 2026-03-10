# JARVIS V20 - Bezpečnostní Audit (Fáze 1)

## 1. KRITICKÉ CHYBY (Critical)

### 1.1 Přímé spuštění shellu přes `run_command` s minimální filtrací
- **Popis problému:** Nástroj `run_command` předává vstup od modelu přímo do `subprocess.run(..., shell=True)` a blokuje pouze několik textových substringů (`rm -rf`, `del /`, `format`, `shutdown`). Neprobíhá allowlist příkazů, sandboxing, oddělení práv, escapování argumentů ani validace struktury příkazu.
- **Riziko:** Jde o klasický Remote Code Execution kanál. Útočník nebo halucinující LLM může spustit libovolné shell příkazy, kombinovat je pomocí `;`, `&&`, subshellů, přesměrování, curl/wget, mazání dat, exfiltraci tajemství nebo laterální pohyb. Substringová blokace je triviálně obejitelná (např. jinými utilitami, rozdělením příkazů, base64 dekódováním, Python one-linery, proměnnými shellu apod.).
- **Umístění v kódu:** `jarvis_tools/__init__.py`, funkce `_tool_run_command`, řádky 252-271.
- **Návrh opravy:** Nepoužívat `shell=True` pro nedůvěryhodný vstup. Zavést striktní allowlist povolených příkazů a argumentů, spouštět přes pole argumentů, omezit pracovní adresář, prostředí a oprávnění procesu, ideálně využít sandbox/namespace/container. Auditovat a logovat původ příkazu. Pro citlivé operace zavést explicitní schvalovací vrstvu.

### 1.2 Libovolný zápis do souborového systému bez omezení cesty
- **Popis problému:** `write_file` používá `Path(fp).resolve()` a následně bez dalších kontrol zapisuje na výslednou absolutní cestu. Není vynucen žádný povolený root adresář, není blokována práce mimo workspace a není řešeno přepisování citlivých souborů.
- **Riziko:** LLM nebo útočník může přepsat konfigurační soubory, SSH klíče, shell profily, aplikační kód, systémové soubory dostupné pod právy procesu nebo perzistentní data. `resolve()` sama o sobě nechrání před path traversal; naopak traversal normalizuje do absolutní cesty, která je poté akceptována.
- **Umístění v kódu:** `jarvis_tools/__init__.py`, funkce `_tool_write_file`, řádky 292-303.
- **Návrh opravy:** Zavést bezpečný workspace root a ověřovat, že výsledná cesta je jeho potomkem. Blokovat zápisy mimo povolené adresáře, zakázat přepis vybraných souborů, ošetřit symlinky a přidat volitelné režimy `append/create-only/overwrite`.

### 1.3 Libovolné čtení souborů bez omezení cesty
- **Popis problému:** `read_file` stejně jako `write_file` pouze resolve-ne cestu a přečte soubor, pokud existuje. Chybí omezení na projektový workspace, ochrana před čtením tajemství a kontrola typu souboru.
- **Riziko:** Možný únik tajemství z prostředí, SSH klíčů, tokenů, konfiguračních souborů, databázových credentialů či jiných citlivých dat. I když je čtení omezeno na prvních 5000 znaků, pro exfiltraci tajemství to zcela stačí.
- **Umístění v kódu:** `jarvis_tools/__init__.py`, funkce `_tool_read_file`, řádky 304-316.
- **Návrh opravy:** Stejně jako u zápisu vynutit povolený root, zablokovat čtení citlivých cest a symlink traversal, zavést allowlist přípon nebo explicitní politiku přístupu.

### 1.4 „Sandbox“ v `run_python` není skutečný sandbox
- **Popis problému:** `run_python` zapisuje kód do souboru a spouští ho běžným interpretem `sys.executable`. Ochrana stojí jen na regex blokaci několika importů a výrazů. Nejsou použity systémové sandboxing mechanismy, omezení syscallů, CPU/memory limity, síťová izolace ani filesystem jail.
- **Riziko:** Regex blacklist lze obcházet mnoha způsoby: nepřímými importy, dynamickou konstrukcí názvů, využitím builtin objektů, modulů dostupných bez explicitního `import`, čtením/zápisem souborů přes standardní API, nebo zneužitím již dostupných funkcí interpretu. Výsledkem může být spuštění libovolného Python kódu s právy procesu JARVIS.
- **Umístění v kódu:** `jarvis_tools/__init__.py`, funkce `_tool_run_python`, řádky 501-605.
- **Návrh opravy:** Přesunout běh kódu do skutečně izolovaného prostředí (např. kontejner, seccomp, nsjail, firejail, samostatný low-privilege worker). Zavést limity CPU/RAM/FS/network, readonly filesystem a explicitní IPC politiku. Blacklist regexy nepovažovat za bezpečnostní kontrolu.

### 1.5 Duplikované flushování WAL vede k nekonzistentnímu a nekontrolovanému růstu logu
- **Popis problému:** `WriteAheadLog.flush()` při každém flushi appenduje posledních 50 položek z in-memory `_entries` do WAL souboru, aniž by evidoval, které záznamy už byly flushnuty. Stejná data tak mohou být do souboru zapisována opakovaně.
- **Riziko:** Auditní stopa i recovery log se nafukují duplicitami, může dojít k nekonzistentní rekonstrukci stavu, zrychlené rotaci WAL, růstu diskové spotřeby a degradaci recovery. U systému spoléhajícího na WAL jde o integritní problém perzistentního stavu.
- **Umístění v kódu:** `jarvis_memory/wal.py`, funkce `flush`, řádky 307-330; související background loop řádky 224-236.
- **Návrh opravy:** Evidovat offset/poslední flushnutý index nebo používat write-through režim po jednotlivých položkách. Recovery musí umět deduplikovat `entry_id`. Současně přidat testy na opakovaný flush a kontrolu integrity po restartu.

## 2. VYSOKÉ RIZIKO (High)

### 2.1 `call_json` slepě důvěřuje výstupu LLM po „opravě“ přes `json_repair`
- **Popis problému:** `CzechBridgeClient.call_json` odešle prompt modelu, získá textový výstup a bez dalšího schématického ověření ho předá do `json_repair.loads(...)`. Pokud parsování projde, vrací se výsledek přímo volajícím vrstvám.
- **Riziko:** LLM může vrátit sémanticky škodlivý, nekompletní nebo strukturálně nečekaný JSON, který `json_repair` „opraví“ do syntakticky validní podoby. Tím se zvyšuje riziko tiché akceptace zkažených dat. To je zvlášť nebezpečné při výběru nástrojů, plánování a orchestraci, protože systém následně vykonává akce podle neověřeného JSON.
- **Umístění v kódu:** `jarvis_core/__init__.py`, metoda `CzechBridgeClient.call_json`, řádky 68-95.
- **Návrh opravy:** Po parsování vždy validovat přes explicitní Pydantic schéma pro daný typ odpovědi (`route`, `suggested_tools`, `sub_goals`, `tool`, `params`, atd.). Logovat, kdy došlo k repair režimu, a v citlivých případech repair odpovědi raději odmítat.

### 2.2 Orchestrátor nevaliduje JSON odpovědi z LLM před použitím
- **Popis problému:** `_master_orchestrate` pouze ověří, že v `result` existuje klíč `route`, a pak vrací celý objekt. Neověřuje se, zda `route` patří do povolené množiny, zda `suggested_tools` jsou validní názvy nástrojů ani zda `direct_response` není zneužitelně velký či škodlivý.
- **Riziko:** Chybné nebo manipulované JSON odpovědi mohou měnit tok aplikace, přesměrovat dotaz do nevhodné exekuční cesty nebo způsobit nečekané chování. V kombinaci s nebezpečnými tools jde o významné zvýšení útočné plochy.
- **Umístění v kódu:** `orchestrator.py`, metoda `_master_orchestrate`, řádky 105-142.
- **Návrh opravy:** Validovat odpověď proti schématu orchestrace, normalizovat `route`, filtrovat `suggested_tools` na známé nástroje a zavést bezpečný fallback při jakékoli odchylce.

### 2.3 ReAct generuje akce z LLM bez lokální validační vrstvy
- **Popis problému:** `_generate_action_v2` očekává JSON s klíči `tool`, `params`, `parallel`, `confidence`, ale výsledek neprochází `validate_tool_params`. V `_execute_tool` se pak tool funkce volají přímo s parametry.
- **Riziko:** I když nástrojové funkce dělají dílčí kontroly, chybí centrální enforcement schématu. To zvyšuje šanci na neočekávané parametry, chybové stavy, nekonzistentní typy a obcházení byznys pravidel. U nebezpečných tools jde o zásadní slabinu.
- **Umístění v kódu:** `reasoning/react_v2.py`, `_generate_action_v2` řádky 234-266, `_execute_tool` řádky 279-289; validační funkce existuje v `jarvis_tools/__init__.py`, řádky 143-179, ale zde se nepoužívá.
- **Návrh opravy:** Před každým spuštěním nástroje volat `validate_tool_params`, zakázat neznámé klíče, vynutit typy a logovat odmítnuté akce. Pro vysokorizikové nástroje přidat ještě samostatnou autorizační vrstvu.

### 2.4 `run_command` a `run_python` mají timeout, ale chybí resource limity a izolace prostředí
- **Popis problému:** Oba nástroje mají časový limit (`30s`, resp. max `120s`), ale neřeší limity paměti, počtu procesů, otevřených souborů, CPU nebo síťové komunikace.
- **Riziko:** Útočník může vyvolat DoS přes fork-bomby, memory blowup, extrémní output, zahlcení disku či síťové požadavky. Timeout sám o sobě neřeší spotřebu prostředků před vypršením limitu.
- **Umístění v kódu:** `jarvis_tools/__init__.py`, `_tool_run_command` řádky 260-268, `_tool_run_python` řádky 562-569.
- **Návrh opravy:** Zavést OS-level limity (`resource`, cgroups, container quotas), omezit stdout/stderr, zakázat síť, a používat izolovaný worker proces s nízkými oprávněními.

### 2.5 Odpovědi z LLM jsou při chybě často tiše degradovány na `None`
- **Popis problému:** `call_json`, `call_stream`, `translate_to_en`, `translate_to_cz` a další vrstvy často zachytí široké `Exception` a vrací `None` nebo původní text bez rozlišení typu selhání.
- **Riziko:** Systém ztrácí možnost odlišit síťový výpadek, rate-limit, nevalidní JSON, nečekaný formát odpovědi nebo interní chybu. To komplikuje audit, observabilitu i bezpečnostní reakce, protože chyba se může tvářit jako „běžný fallback“.
- **Umístění v kódu:** `jarvis_core/__init__.py`, řádky 75-95, 96-136, 138-180; `orchestrator.py`, řádky 125-142; `planning/hierarchical_planner.py`, řádky 255-276; `reasoning/react_v2.py`, více bloků try/except.
- **Návrh opravy:** Zpřesnit výjimky, zavést chybové typy a důsledné logování s klasifikací selhání. Fallback používat jen pro známé scénáře a neskrývat kritické chyby.

### 2.6 `call_stream` ignoruje chybné JSON chunk-y bez signalizace
- **Popis problému:** Při streamu se každý řádek parsuje přes `json.loads`; pokud parsování selže, výjimka se potichu ignoruje (`except Exception: pass`).
- **Riziko:** Výstup modelu může být částečně ztracen nebo poškozen bez jakékoli indikace. To může ovlivnit reasoning chain, generování odpovědí i bezpečnostní analýzu incidentů.
- **Umístění v kódu:** `jarvis_core/__init__.py`, metoda `call_stream`, řádky 121-132.
- **Návrh opravy:** Logovat poškozené chunk-y, počítat míru chybovosti streamu a při překročení prahu stream ukončit jako chybný.

## 3. STŘEDNÍ RIZIKO (Medium)

### 3.1 Circuit breaker není thread-safe
- **Popis problému:** `CircuitBreaker` pracuje se sdíleným mutable stavem (`_state`, `_failure_count`, `_success_count`, `_failure_history`) bez jakéhokoli zámku. Přitom architektura obsahuje paralelní executor a swarm koncept.
- **Riziko:** Při souběžném použití může docházet k race conditions, nekonzistentnímu otevírání/zavírání okruhu a nepredikovatelnému blokování/propouštění akcí.
- **Umístění v kódu:** `jarvis_reasoning/circuit_breaker.py`, prakticky celý objekt, zejména řádky 49-188.
- **Návrh opravy:** Obalit čtení/zápisy stavu do `threading.Lock/RLock`, případně breaker přesunout do single-thread vlastnictví s message passing modelem.

### 3.2 Stav circuit breakeru není sdílen mezi agenty a instancemi
- **Popis problému:** `ReActLoopV2` si vytváří vlastní `CircuitBreaker` v konstruktoru. Neexistuje centrální breaker pro všechny agenty, plánovače nebo paralelní exekuce.
- **Riziko:** Pokud jeden agent opakovaně selhává na stejné akci, jiné agentní instance o tom nemusí vědět a mohou chybu dál reprodukovat. Ochrana proti smyčkám je tak lokální, ne systémová.
- **Umístění v kódu:** `reasoning/react_v2.py`, řádek 57.
- **Návrh opravy:** Zavést breaker na úrovni sdílené služby nebo minimálně sdílený registr breakerů podle typu úlohy/nástroje.

### 3.3 Detekce selhání v ReAct smyčce je založena na substringu `"error"`
- **Popis problému:** ReAct rozhoduje, zda zaznamenat success/failure do circuit breakeru podle toho, zda observation obsahuje substring `error`.
- **Riziko:** Jde o velmi křehkou heuristiku. Falešně pozitivní i falešně negativní případy jsou pravděpodobné. Například nástroj může vracet `❌`, `Blocked`, `Not found`, `timeout`, nebo naopak slovo `error` v neškodném kontextu.
- **Umístění v kódu:** `reasoning/react_v2.py`, řádky 160-164.
- **Návrh opravy:** Standardizovat návratové objekty nástrojů (`status`, `message`, `code`) místo parsování textu. Circuit breaker navazovat na explicitní status.

### 3.4 `_should_stop` může ukončit smyčku na základě běžných slov
- **Popis problému:** Stop podmínka hledá ve výstupu indikátory jako `success`, `done`, `complete`, `answer:`, `final:`.
- **Riziko:** Reasoning se může předčasně ukončit, pokud se tato slova objeví v běžném textu výstupu nástroje. Naopak může zbytečně pokračovat, když úloha skončila jinak.
- **Umístění v kódu:** `reasoning/react_v2.py`, řádky 291-295.
- **Návrh opravy:** Používat explicitní strukturovaný signál dokončení z modelu nebo z vykonaného plánu, ne substring matching.

### 3.5 „Parallel“ execution v ReAct není skutečně paralelní
- **Popis problému:** `_execute_parallel` v `ReActLoopV2` pouze iteruje přes akce sekvenčně. Skutečný `ParallelToolExecutor` sice existuje, ale zde se nevyužívá.
- **Riziko:** Nejde přímo o bezpečnostní chybu, ale zvyšuje to nepředvídatelnost architektury a může vést ke špatným předpokladům o souběhu, sdílení stavu a testovacím scénářům.
- **Umístění v kódu:** `reasoning/react_v2.py`, řádky 267-277; skutečný paralelní executor je v `tools/parallel_executor.py`.
- **Návrh opravy:** Buď přiznat sekvenční chování, nebo skutečně napojit `ParallelToolExecutor` a doplnit thread-safety audit všech sdílených komponent.

### 3.6 Potenciál deadlock/race v paměťových vrstvách kvůli vnořenému lockování a I/O pod zámkem
- **Popis problému:** Některé komponenty ukládají data na disk uvnitř kritické sekce. Např. `ProceduralMemory.record_failure()` drží `_lock` a uvnitř volá `_save_failures()`, která se znovu snaží pracovat se stejným zámkem a provádí file I/O. Díky použití `RLock` nejde o okamžitý deadlock, ale kritická sekce je dlouhá a zahrnuje pomalé operace.
- **Riziko:** Při vyšší souběžnosti roste latence a riziko contention. Pokud by se do budoucna kombinovaly různé zámky v jiném pořadí nebo se z `RLock` stal běžný `Lock`, vznikne deadlock velmi snadno.
- **Umístění v kódu:** `jarvis_memory/procedural_memory.py`, řádky 254-283, 315-358, 176-206; obdobně `jarvis_memory/wal.py`, řádky 252-269 a 317-330.
- **Návrh opravy:** Minimalizovat práci pod zámkem, oddělit mutaci in-memory stavu od diskového zápisu, zavést jasný lock ordering a přidat concurrency testy.

### 3.7 Background vlákna nejsou koordinována jednotným shutdown mechanismem
- **Popis problému:** `ConsolidationScheduler` má `stop_event` a korektní `stop()`, ale `ProceduralMemory` používá nekonečnou smyčku s `threading.Event().wait(...)` bez uchovávaného stop eventu a bez `shutdown()`. WAL flush thread používá `_shutdown`, ale thread handle se neukládá.
- **Riziko:** Nečisté ukončení procesu, závody při shutdown, nedoflushovaná data a obtížné testování. U dlouho běžících agentů to znamená i únik vláken a nejasný lifecycle.
- **Umístění v kódu:** `jarvis_memory/procedural_memory.py`, řádky 208-223; `jarvis_memory/wal.py`, řádky 224-236; `jarvis_memory/consolidation.py`, řádky 74-216.
- **Návrh opravy:** Zavést konzistentní lifecycle API (`start/stop/shutdown/join`) pro všechny background služby a centrální orchestrace shutdown.

### 3.8 SIGINT handler je definován pouze v `jarvis_core`, ale V20 orchestrátor jej explicitně neintegruje
- **Popis problému:** V `jarvis_core/__init__.py` je globální `_emergency_stop` a `signal.signal(SIGINT, _handle_sigint)`, ale `JarvisV20` v `orchestrator.py` tento mechanismus nepoužívá při smyčkách plánování/reasoningu.
- **Riziko:** Ctrl+C sice nastaví event, ale V20 cesty jej nekontrolují, takže dlouhé operace nemusí být přerušitelné konzistentně. To je spíš provozní než čistě bezpečnostní problém, ale v incident response je důležitý.
- **Umístění v kódu:** `jarvis_core/__init__.py`, řádky 30-43; v `orchestrator.py` a `reasoning/react_v2.py` není návazné použití.
- **Návrh opravy:** Propagovat stop token do planneru, reasoningu, swarmu i background workerů a pravidelně jej kontrolovat.

### 3.9 `MemoryManagerV2` používá pravděpodobně neexistující interní atribut `_semantic`
- **Popis problému:** `get_memory_stats()` testuje `hasattr(self._memory, '_semantic')`, zatímco `CognitiveMemory` používá atribut `semantic`.
- **Riziko:** Funkce vrací nepřesné statistiky a skrývá chyby. Není to přímá bezpečnostní chyba, ale snižuje spolehlivost observability a auditních dat.
- **Umístění v kódu:** `memory/manager_v2.py`, řádky 87-95.
- **Návrh opravy:** Opravit na veřejné API `self._memory.semantic` nebo zavést standardizované rozhraní pro statistiky.

## 4. NÍZKÉ RIZIKO (Low)

### 4.1 Pydantic validace parametrů existuje, ale není vynucena univerzálně
- **Popis problému:** `validate_tool_params()` a modely jako `RunPythonParams`, `WriteFileParams` apod. jsou implementovány kvalitně, ale jejich použití není centrálně vynuceno ve všech exekučních cestách.
- **Riziko:** Spíš architektonická nekonzistence než přímá exploitační chyba. Přesto jde o promarněnou obrannou vrstvu.
- **Umístění v kódu:** `jarvis_tools/__init__.py`, řádky 41-179.
- **Návrh opravy:** Udělat z validace povinný krok před každým tool call.

### 4.2 `forget` validuje `fact_id` jen velmi volně
- **Popis problému:** Regex `^[a-f0-9\-]+$` povolí mnoho řetězců, které nejsou UUID ani interní ID formát faktů.
- **Riziko:** Nízké. Nevede přímo k RCE, ale generuje nepřesné UX a oslabuje konzistenci rozhraní.
- **Umístění v kódu:** `jarvis_tools/__init__.py`, řádky 403-405.
- **Návrh opravy:** Validovat proti skutečnému formátu ID nebo ověřit existenci cílového záznamu před operací.

### 4.3 `list_dir` nemá omezení na workspace
- **Popis problému:** Stejně jako read/write lze listovat libovolné dostupné adresáře.
- **Riziko:** Samostatně nízké, ale v kombinaci s `read_file` usnadňuje průzkum filesystemu a následnou exfiltraci.
- **Umístění v kódu:** `jarvis_tools/__init__.py`, řádky 423-435.
- **Návrh opravy:** Omezit na povolené rooty a filtrovat citlivé cesty.

### 4.4 Background analýza procedurální paměti používá nově vytvořený `Event()` jen jako sleep mechaniku
- **Popis problému:** `threading.Event().wait(...)` je voláno na dočasném objektu, který nikdo nikdy nenastaví.
- **Riziko:** Nízké, ale jde o code smell a komplikuje budoucí stop/shutdown.
- **Umístění v kódu:** `jarvis_memory/procedural_memory.py`, řádek 212.
- **Návrh opravy:** Použít persistentní `_stop_event` sdílený vláknem.

## 5. DOPORUČENÍ A OPTIMALIZACE

1. **Zavést bezpečnostní politiku pro tools**
   - rozdělit tools na low-risk / high-risk,
   - vyžadovat explicitní schválení pro `run_command`, `run_python`, zápis do souborů,
   - ukládat auditní záznamy o tom, kdo a proč akci spustil.

2. **Centralizovat validaci LLM JSON odpovědí**
   - každá odpověď z `call_json` musí mít svůj Pydantic model,
   - `json_repair` používat jen jako pomocný parser, ne jako důvod k automatické důvěře,
   - při repair režimu přidat varování do logů a telemetry.

3. **Převést textové výsledky tools na strukturované návratové objekty**
   - např. `{"status": "ok|error|blocked", "message": "...", "data": ...}`,
   - tím se zlepší circuit breaker, stop logika i metriky.

4. **Zavést skutečný sandbox pro exekuci kódu a příkazů**
   - oddělený worker s minimálními právy,
   - cgroups / namespaces / seccomp,
   - vypnutá síť a omezený filesystem.

5. **Opravit WAL semantiku**
   - zajistit idempotentní flush,
   - přidat testy recovery po více flushech,
   - evidovat offset flushnutých položek,
   - kontrolovat checksum i unikátnost `entry_id`.

6. **Auditovat thread-safety všech sdílených služeb**
   - `CircuitBreaker`, `ParallelToolExecutor`, memory vrstvy,
   - definovat lock ordering,
   - omezit file I/O uvnitř kritických sekcí.

7. **Sjednotit shutdown a stop tokeny**
   - planner, reasoning, swarm, WAL, procedural memory a consolidation scheduler musí respektovat společný cancellation token,
   - zajistit deterministické ukončení při SIGINT/SIGTERM.

8. **Zlepšit observabilitu a detekci chyb**
   - rozlišovat chyby sítě, parsingu, validace a timeouts,
   - nepolykat výjimky bez logu,
   - přidat bezpečnostní metriky (počty blokovaných akcí, repair JSON odpovědí, open circuit stavů).

## 6. AKČNÍ PLÁN (Action Plan)

### Fáze A — Okamžité zásahy
1. Zakázat nebo výrazně omezit `run_command` a `run_python` v produkčním režimu.
2. Zavést workspace boundary pro `read_file`, `write_file`, `list_dir`.
3. Přidat povinnou validaci `validate_tool_params()` před spuštěním každého tool call.
4. Opravit WAL flush tak, aby nezapisoval duplicitní položky.

### Fáze B — Stabilizace architektury
5. Založit Pydantic schémata pro:
   - orchestration response,
   - planner sub-goals,
   - ReAct action selection,
   - final answer metadata.
6. Upravit `call_json`, aby vracel strukturované chyby místo tichého `None`.
7. Standardizovat návratové hodnoty nástrojů na strukturovaný formát.
8. Udělat circuit breaker thread-safe a rozhodnout, zda má být sdílen globálně nebo per-agent.

### Fáze C — Hardening a dlouhodobá údržba
9. Přesunout exekuci příkazů/kódu do izolovaného workeru.
10. Doplnit concurrency testy pro WAL, procedural memory a planner/reasoning vrstvy.
11. Zavést graceful shutdown pro všechna background vlákna.
12. Rozšířit audit o Fázi 2: síťová vrstva, ChromaDB integrace, swarm koordinace a supply-chain závislosti.

---

## Poznámky k auditu
- Audit byl proveden pouze statickou analýzou kódu podle zadaných oblastí.
- V této fázi nebyl měněn aplikační kód, pouze vytvořena auditní zpráva.
- Nejzávažnější nálezy souvisí s nedůvěryhodným LLM vstupem, který je v několika cestách překládán přímo do exekuce nástrojů nebo práce se souborovým systémem bez dostatečných bezpečnostních hranic.

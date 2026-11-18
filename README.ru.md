# rulesets

[English](README.md) | **Русский**

Единый источник правил фильтрации и маршрутизации. Правится **только** [`rules.yml`](rules.yml);
всё остальное собирает CI и публикует в ветку [`release`](../../tree/release).

| Клиент | Что собирается | Где лежит в `release` |
|---|---|---|
| podkop (OpenWrt) | `.lst`: домены и IPv4-подсети, по спискам и сводные по действию | `podkop/` |
| sing-box | rule-set `.json` (version 3) и `.srs` | `sing-box/` |
| Throne | удалённый маршрутный профиль `throne://route/…` | `throne/` |
| Tixati | IP-фильтр `label:CIDR` (IPv4 и IPv6), фильтр Peer ID | `tixati/` |
| qBittorrent | IP-фильтр `ipfilter.p2p`, скрипт обновления | `qbittorrent/` |
| qBittorrent Enhanced | всё то же + `peer_blacklist.txt` (Peer ID) | `qbittorrent/` |

Полный список файлов со ссылками — в `README.md` и `index.json` ветки `release`.

## Быстрый старт

Скопируйте ссылку и вставьте в клиент. Все ссылки ведут в ветку `release` и всегда отдают последнюю сборку.

### podkop (OpenWrt)

LuCI → **Services → Podkop**. Списки обновляются по расписанию самого podkop.

1. Добавьте секцию с типом подключения **Block** → *Remote subnet lists*:
   ```
   https://raw.githubusercontent.com/Gesugao-san/rulesets/release/podkop/all-block.subnets.lst
   ```
2. В вашей секции **Proxy** → *Remote domain lists*:
   ```
   https://raw.githubusercontent.com/Gesugao-san/rulesets/release/podkop/all-proxy.domains.lst
   ```
3. Save & Apply.

IPv6 в podkop не попадает: его списки подсетей принимают только IPv4.

### Throne

1. Настройки маршрутизации → добавить **удалённый** (remote) профиль маршрутов, URL:
   ```
   https://raw.githubusercontent.com/Gesugao-san/rulesets/release/throne/selective.txt
   ```
2. Включите автообновление и выберите профиль.

При каждом обновлении Throne перезаписывает правила удалённого профиля — личные правила держите в отдельном локальном профиле.
Ссылки на GitHub Throne берёт через jsDelivr, поэтому изменения доходят с задержкой кэша.

### Tixati

1. **IP Filter** (значок крепостной стены на панели) → **Add** → URL источника, затем задайте интервал автообновления:
   ```
   https://raw.githubusercontent.com/Gesugao-san/rulesets/release/tixati/all-block.txt
   ```
2. **Settings → Peers → Client Filter → Peer ID** → «never allow»: добавьте каждую строку из
   ```
   https://raw.githubusercontent.com/Gesugao-san/rulesets/release/tixati/peerid-filter.txt
   ```
   Импорта для этого фильтра в Tixati нет, строки добавляются вручную.

### qBittorrent / qBittorrent Enhanced (Windows)

qBittorrent не умеет брать фильтр по URL, поэтому его обновляет скрипт.

1. Скачайте скрипт и один раз запустите его в PowerShell:
   ```powershell
   iwr https://raw.githubusercontent.com/Gesugao-san/rulesets/release/qbittorrent/update-ipfilter.ps1 -OutFile "$env:LOCALAPPDATA\qBittorrent\update-ipfilter.ps1"
   powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\qBittorrent\update-ipfilter.ps1"
   ```
   Для обычного qBittorrent добавьте `-SkipPeerBlacklist` ко второй команде.
2. qBittorrent → **Настройки → Соединение → Фильтрация IP** → включить и вставить в окно выбора файла путь:
   ```
   %LOCALAPPDATA%\qBittorrent\rulesets-ipfilter.p2p
   ```
3. Ежедневное обновление через Планировщик заданий (выполнить один раз):
   ```powershell
   $a = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$env:LOCALAPPDATA\qBittorrent\update-ipfilter.ps1`""
   Register-ScheduledTask -TaskName 'rulesets qBittorrent' -Action $a -Trigger (New-ScheduledTaskTrigger -Daily -At 4:20)
   ```

Enhanced читает `peer_blacklist.txt` только при запуске: после обновления перезапустите qBittorrent (скрипт завершается с кодом 2 и процесс не трогает).
`peer_whitelist.txt` скрипт не создаёт никогда: при его наличии Enhanced пропускает только перечисленных в нём пиров.

### Закрепление сборки

Каждая сборка, которая меняет `release`, также помечается тегом `build-YYYY-MM-DD-N` (N — номер прогона CI).
Чтобы закрепить клиент на сборке или откатиться, используйте в ссылке `/<тег>/` вместо `/release/`.
Профили Throne внутри тега всё равно берут `.srs` из ветки `release`.

В ветке `release` есть свои `README.md` и `README.ru.md` с прямыми ссылками на каждый файл.

## Как править

1. Изменить `rules.yml` (можно прямо в веб-интерфейсе GitHub).
2. Открыть PR — CI прогонит проверки и тесты, но ничего не опубликует.
3. После слияния в `main` CI соберёт и запушит `release`.

Сборка падает, если в `rules.yml`:

- частный/служебный диапазон или подсеть с ненулевыми битами хоста;
- домен глубже второго уровня без `sld_exception: <причина>`;
- запись в списке `block` без `evidence`;
- Peer ID длиннее 8 символов (Enhanced сравнивает только первые 8) или с пробелом;
- дубли или подсеть, вложенная в другую;
- профиль Throne ссылается на несуществующий список.

Локально:

```sh
pip install pyyaml
python3 tools/build.py --out dist                      # без .srs
python3 tools/build.py --out dist --sing-box sing-box  # с .srs
python3 -m unittest tools/test_build.py -v
```

## Чего здесь нет и почему

- **Фильтра по Peer ID для podkop и Throne** — на уровне сети видны только IP и домены.
- **Блокировки хостингов целиком** (AWS, IONOS, NFOrce, SoftLayer, Contabo): доказательства
  разной силы, а у NFOrce, например, живут и настоящие сидбоксы. Каждая запись — только с `evidence`.

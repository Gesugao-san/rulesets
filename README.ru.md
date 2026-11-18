# rulesets

[English](README.md) | **Русский**

Правила фильтрации и маршрутизации в одном месте: все списки живут в [`rules.yaml`](rules.yaml),
а CI собирает из него форматы для каждого клиента в ветку [`release`](../../tree/release).

| Формат | Содержимое | Клиент → файл в `release` |
|---|---|---|
| бинарный rule-set sing-box `.srs` | домены и IP-подсети | [sing-box](https://sing-box.sagernet.org) (любая) → `sing-box/<list>.srs`<br>[Karing](https://github.com/KaringX/karing) (Android, iOS, Windows, macOS, Linux) → тот же файл<br>[Throne](https://github.com/throneproj/Throne), [NekoBox](https://github.com/qr243vbi/nekobox) берут его по ссылке |
| исходник rule-set sing-box `.json` (version 3) | то же, в читаемом виде | [sing-box](https://sing-box.sagernet.org) → `sing-box/<list>.json` |
| ссылка на маршрутный профиль Throne `throne://route/…` | профиль со ссылками на `.srs` | [Throne](https://github.com/throneproj/Throne) (Windows, Linux, macOS) → `throne/selective.txt` |
| ссылка подписки Throne `throne://remoteroute/…` | подписка на профиль выше в один шаг | [Throne](https://github.com/throneproj/Throne) → `throne/selective.remoteroute.txt` |
| простые правила NekoBox / Throne `ruleset:<ссылка>` | ссылки на `.srs`, по строке на список | [NekoBox](https://github.com/qr243vbi/nekobox) (Windows, Linux) → `nekobox/desktop-<action>.txt` |
| строки маршрутизации в стиле v2ray `domain:` / CIDR | домены и IP-подсети для ручной вставки | [NekoBox for Android](https://github.com/MatsuriDayo/NekoBoxForAndroid) (Android) → `nekobox/android-<action>.domains.txt`, `….ips.txt` |
| простой список `.lst` | по одному домену или IPv4-подсети в строке | [podkop](https://github.com/itdoginfo/podkop) (OpenWrt) → `podkop/all-<action>.domains.lst`, `….subnets.lst` |
| P2P с CIDR `.p2p.txt` (`label:CIDR`) | IP-фильтр, IPv4 и IPv6 | [Tixati](https://www.tixati.com) (Windows, Linux) → `tixati/all-block.p2p.txt` |
| PeerGuardian P2P `.p2p` (`label:начало-конец`) | IP-фильтр, IPv4 и IPv6 | [qBittorrent](https://www.qbittorrent.org), [qBittorrent Enhanced](https://github.com/c0re100/qBittorrent-Enhanced-Edition) (Windows, Linux, macOS) → `qbittorrent/ipfilter.p2p` |
| фильтр Peer ID: шаблон / PCRE | префиксы Peer ID клиентов-шпионов | [Tixati](https://www.tixati.com) → `tixati/peerid-filter.txt` (`-XX0001-*`)<br>[qBittorrent Enhanced](https://github.com/c0re100/qBittorrent-Enhanced-Edition) → `qbittorrent/peer_blacklist.txt` (`^-XX0001- .*`) |
| скрипт PowerShell `.ps1` | обновляет IP-фильтр и список Peer ID | [qBittorrent](https://www.qbittorrent.org), [qBittorrent Enhanced](https://github.com/c0re100/qBittorrent-Enhanced-Edition) (Windows) → `qbittorrent/update-ipfilter.ps1` |
| список ссылок `.txt` | ссылки на внешние `.srs` (записи `ruleset:`) | [Karing](https://github.com/KaringX/karing), [sing-box](https://sing-box.sagernet.org), [podkop](https://github.com/itdoginfo/podkop) → `external/all-<action>.txt` |
| список CIDR `.txt`, `.json`, `.csv` | развёрнутые `asn`/`country`/`continent`, карта rule-set'ов, отчёт об исходных AS | для проверки, не для клиентов → `resolved/`, `review.csv` |

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
3. По желанию — внешние rule-set'ы (записи `ruleset:`): podkop принимает ссылки на `.srs` как удалённые списки, по одной на строку из
   ```
   https://raw.githubusercontent.com/Gesugao-san/rulesets/release/external/all-proxy.txt
   ```
4. Save & Apply.

IPv6 в podkop не попадает: его списки подсетей принимают только IPv4.

### Throne

**В один шаг:** скопируйте ссылку, откройте в Throne управление маршрутами и нажмите **Import** — он читает буфер обмена,
спрашивает подтверждение и добавляет удалённый профиль с автообновлением:
```
throne://remoteroute/aHR0cHM6Ly9yYXcuZ2l0aHVidXNlcmNvbnRlbnQuY29tL0dlc3VnYW8tc2FuL3J1bGVzZXRzL3JlbGVhc2UvdGhyb25lL3NlbGVjdGl2ZS50eHQjR2VzdSUyMHNlbGVjdGl2ZQ==
```
**Вручную:** добавьте **удалённый** (remote) профиль маршрутов с URL ниже и включите автообновление:
```
https://raw.githubusercontent.com/Gesugao-san/rulesets/release/throne/selective.txt
```

Правила идут от точных к широким: блок-списки, затем `ru-direct`, списки сервисов (`telegram`, `discord`, `youtube`,
`services`, `ru-extra`) и только потом широкие внешние наборы `ru-blocked` (proxy) и `ru-broad` (direct).
Поэтому явный выбор в `rules.yaml` всегда важнее большого внешнего списка; порядок задаётся в `profiles` в `rules.yaml`.

При каждом обновлении Throne перезаписывает правила удалённого профиля — личные правила держите в отдельном локальном профиле.
Ссылки на GitHub Throne берёт через jsDelivr, поэтому изменения доходят с задержкой кэша.
Если вставить в **Import** содержимое самого `throne/selective.txt`, получится разовая локальная копия без обновлений.

### NekoBox (ПК)

Настройки маршрутизации → маршрут нужного исходящего (Block / Proxy) → вставить строки из:
```
https://raw.githubusercontent.com/Gesugao-san/rulesets/release/nekobox/desktop-block.txt
```
```
https://raw.githubusercontent.com/Gesugao-san/rulesets/release/nekobox/desktop-proxy.txt
```
Каждая строка — `ruleset:<ссылка на .srs>`; NekoBox сам скачивает rule-set'ы, обновления приходят автоматически.

### NekoBox for Android

В NekoBox для Android нет удалённых rule-set'ов — только встроенные `geoip:`/`geosite:`. Правила вставляются текстом и **не** обновляются сами:
Маршрут → новое правило → поле *domain*: строки из первого файла, поле *IP*: из второго, исходящий Block / Proxy.
```
https://raw.githubusercontent.com/Gesugao-san/rulesets/release/nekobox/android-proxy.domains.txt
```
```
https://raw.githubusercontent.com/Gesugao-san/rulesets/release/nekobox/android-block.ips.txt
```
После изменений вставляйте заново. Большие списки (страны, континенты) здесь непрактичны.

### Karing

Правила отвода (Diversion) → **Add New Diversion Group** → вставить ссылку на `.srs` и сохранить → Custom Diversion Group → выбрать группу и задать действие.
По группе на ссылку: `sing-box/<список>.srs` для каждого списка из `rules.yaml`, например
```
https://raw.githubusercontent.com/Gesugao-san/rulesets/release/sing-box/telegram.srs
```
плюс внешние rule-set'ы, по ссылке на строку в
```
https://raw.githubusercontent.com/Gesugao-san/rulesets/release/external/all-proxy.txt
```
```
https://raw.githubusercontent.com/Gesugao-san/rulesets/release/external/all-block.txt
```
На всех платформах одинаково. Документация Karing предупреждает, что `.srs` больше 3 МБ могут не влезть в память на Android и iOS — учитывайте это для стран и континентов.

### Tixati

1. **IP Filter** (значок крепостной стены на панели) → **Add** → URL источника, затем задайте интервал автообновления:
   ```
   https://raw.githubusercontent.com/Gesugao-san/rulesets/release/tixati/all-block.p2p.txt
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

К каждому тегу также создаётся [GitHub Release](../../releases), где каждый файл приложен отдельно (папка становится префиксом:
`podkop/all-block.subnets.lst` → `podkop.all-block.subnets.lst`). Хранятся 30 последних релизов; старые теги остаются.

В ветке `release` есть свои `README.md` и `README.ru.md` с прямыми ссылками на каждый файл.

## Как править

1. Изменить `rules.yaml` (можно прямо в веб-интерфейсе GitHub).
2. Открыть PR — CI прогонит проверки и тесты, но ничего не опубликует.
3. После слияния в `main` CI соберёт и запушит `release`.

Виды записей: `domain`, `ip`, `peerid`, `asn`, `country`, `continent`, `ruleset`. Список `example` в конце `rules.yaml` показывает каждый;
у него `enabled: false`, поэтому он проверяется при каждой сборке, но никогда не публикуется.

Сборка падает, если в `rules.yaml`:

- частный/служебный диапазон или подсеть с ненулевыми битами хоста;
- домен, который не является своим регистрируемым доменом (eTLD+1 по [Public Suffix List](https://publicsuffix.org/)),
  или сам является публичным суффиксом (`pages.dev`, `discordsays.com`), без `sld_exception: <причина>`;
- `ruleset:`, который не является ни именем из каталога Throne, ни https-ссылкой на `.srs`;
- запись в списке `block` без `evidence`;
- Peer ID длиннее 8 символов (Enhanced сравнивает только первые 8) или с пробелом;
- дубли или подсеть, вложенная в другую;
- профиль Throne ссылается на несуществующий или выключенный список;
- частный/служебный номер AS, неизвестный код страны или континента;
- запись `asn`/`country`/`continent` разворачивается в больше префиксов, чем её `max_prefixes`
  (по умолчанию 16 / 20000 / 200000) — широкая блокировка всегда осознанный выбор.

Локально:

```sh
pip install pyyaml
python3 tools/build.py --out dist                      # без .srs
python3 tools/build.py --out dist --sing-box sing-box  # с .srs
python3 -m unittest tools/test_build.py -v
```

## Когда запускается сборка

| Событие | Условие | Результат |
|---|---|---|
| Пуш в `main` | изменились `rules.yaml`, `tools/**`, `clients/**` или `.github/workflows/build.yml` | тесты, сборка, публикация |
| Pull request | изменились те же пути | только тесты и сборка, ничего не публикуется |
| Расписание | ежедневно в 00:00 UTC (запуски по расписанию могут стартовать на несколько минут позже) | тесты, сборка, публикация — префиксы за `asn`/`country`/`continent` меняются без правок |
| Вручную | **Run workflow** на вкладке Actions | тесты, сборка, публикация |

Правки только в `README.md`, `README.ru.md` или `.gitignore` сборку не запускают.
Если публикация ничего не меняет в `release`, не появляется ни коммита, ни тега, ни GitHub Release.

## Источники данных

Записи `asn`, `country`, `continent` и `ruleset` разворачиваются при сборке; результат сохраняется в `release/resolved/`, так что любое изменение видно диффом.

| Запись | Источник | Примечания |
|---|---|---|
| `asn` | [RIPEstat announced-prefixes](https://stat.ripe.net/docs/data-api/api-endpoints/announced-prefixes) (RIPE NCC) | Данные BGP с коллекторов RIS по всему миру, не только регион RIPE. Берутся только префиксы, анонсируемые на конец двухнедельного окна |
| `country` | [RIPEstat country-resource-list](https://stat.ripe.net/docs/data-api/api-endpoints/country-resource-list) | Строится по статистике делегирования RIR: страна **регистрации**, а не место использования (это не геолокация) |
| `ruleset` | Каталог rule-set'ов Throne: [`srslist.h`](https://github.com/throneproj/routeprofiles/tree/rule-set) в throneproj/routeprofiles | Имя → ссылка на `.srs`, ровно как в Throne (в основном [MetaCubeX/meta-rules-dat](https://github.com/MetaCubeX/meta-rules-dat), `geosite-ru-*` — от [runetfreedom](https://github.com/runetfreedom/russia-v2ray-rules-dat)). Карта сохраняется в `resolved/rulesets.json`, ссылки публикуются в `external/` |
| проверка `domain` | [Public Suffix List](https://publicsuffix.org/) ([MPL 2.0](https://mozilla.org/MPL/2.0/)), снимок в [`tools/data/public_suffix_list.dat`](tools/data/public_suffix_list.dat) | Обе секции, ICANN и частная: `googleapis.com` и `pages.dev` считаются публичными суффиксами |
| `continent` | [GeoNames](https://www.geonames.org/) countryInfo ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)), снимок в [`tools/data/continents.json`](tools/data/continents.json) | Страна → континент, дальше каждая страна как выше. GeoNames относит Россию к `EU`, Турцию к `AS` |

Если RIPEstat или каталог rule-set'ов недоступен, берётся предыдущий снимок из `release` с предупреждением; без снимка сборка падает, а не публикует пустой список.
CI также пересобирает всё ежедневно: префиксы меняются без правок `rules.yaml`.

`release/review.csv` — таблица по каждой записи `ip`: анонсированный префикс, который её покрывает, исходный AS
([RIPEstat prefix-overview](https://stat.ripe.net/docs/data-api/api-endpoints/prefix-overview)) и сколько префиксов этот AS анонсирует.
Она только подсказывает: заслуживает ли небольшой выделенный AS записи `asn`, решается вручную. Неудачный запрос — предупреждение, а не провал сборки.

## Чего здесь нет и почему

- **Фильтра по Peer ID для podkop и Throne** — на уровне сети видны только IP и домены.
- **Блокировки хостингов целиком** (AWS, IONOS, NFOrce, SoftLayer, Contabo): доказательства
  разной силы, а у NFOrce, например, живут и настоящие сидбоксы. Каждая запись — только с `evidence`.

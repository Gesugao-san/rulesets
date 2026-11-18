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

## Подключение

Ниже `$R` = `https://raw.githubusercontent.com/Gesugao-san/rulesets/release`.

### podkop

Сводные файлы подхватывают новые списки сами, без перенастройки роутера.

- Секция с типом подключения **Block** → `remote_subnet_lists`: `$R/podkop/all-block.subnets.lst`
- Секция **Proxy** → `remote_domain_lists`: `$R/podkop/all-proxy.domains.lst`

IPv6 в podkop не попадает: его `.lst` для подсетей принимает только IPv4 (предупреждение видно в сводке CI).

### Throne

Маршруты → новый **удалённый** профиль → URL `$R/throne/selective.txt`, включить автообновление.

При обновлении Throne перезаписывает правила удалённого профиля — личные правила держите в отдельном локальном профиле.
Ссылки на `raw.githubusercontent.com` Throne сам переписывает на jsDelivr, поэтому изменения доходят с задержкой кэша.

### Tixati

- Значок **IP Filter** → Add → URL `$R/tixati/all-block.txt`, задать интервал автообновления.
- Settings → Peers → Client Filter → вкладка **Peer ID** → «never allow»: по строке из `$R/tixati/peerid-filter.txt` (вручную, импорта у Tixati нет).

### qBittorrent / qBittorrent Enhanced

qBittorrent не умеет брать фильтр по URL, поэтому обновлением занимается скрипт:

```powershell
.\update-ipfilter.ps1                      # Enhanced: ipfilter + peer_blacklist
.\update-ipfilter.ps1 -SkipPeerBlacklist   # обычный qBittorrent
```

Один раз указать в qBittorrent: Настройки → Соединение → Фильтрация IP → путь к
`%LOCALAPPDATA%\qBittorrent\gesu-ipfilter.p2p`. Пример планировщика заданий — в шапке скрипта.

Enhanced читает `peer_blacklist.txt` только при запуске: после обновления нужен перезапуск
(скрипт сообщает об этом кодом выхода 2 и сам процесс не трогает). `peer_whitelist.txt` скрипт
не создаёт никогда: при его наличии Enhanced пропускает только перечисленных в нём пиров.

## Чего здесь нет и почему

- **Фильтра по Peer ID для podkop и Throne** — на уровне сети видны только IP и домены.
- **Блокировки хостингов целиком** (AWS, IONOS, NFOrce, SoftLayer, Contabo): доказательства
  разной силы, а у NFOrce, например, живут и настоящие сидбоксы. Каждая запись — только с `evidence`.

# Moments at risk

These NHL Breakaway moments have **original files that could not be reached on IPFS** in the last check
(`python breakaway.py check-ipfs`, then `--recheck` on at least two gateways). "Missing" means no gateway we
asked could serve it. That can mean nobody pins it anymore, or just that it's very cold, so treat it as at risk,
not proven lost.

> **Did you download any of these?** Please check your copies with `python breakaway.py verify`:
> a file marked **original** matches the official sha256 and is the real thing. If you have one, help
> re-pin it (`ipfs add` the file on your own node: it gets the same CID back) or open an issue so
> others know a copy exists. To grab them while the CDN still has them:
> `python breakaway.py covers --at-risk` and `python breakaway.py videos --at-risk`. Note that the CDN serves
> re-encoded videos, so a CDN copy is better than nothing but isn't the original.


> **PARTIAL SCAN.** Not every file has been checked yet (checked/total: video 1,954/1,954, cover 1,954/1,954, card-image 1,086/1,086, cover-16x9 1,953/1,953, thumbnail 996/7,792). Thumbnails are mostly unchecked, so they don't count toward `unchecked` health. 76 file(s) failed twice on up to 4 gateways (`gone`); 256 failed the first pass only and weren't re-checked yet. Anyone can finish the scan: `python breakaway.py check-ipfs --full` (it resumes, skipping files checked in the last 30 days), then `check-ipfs --recheck`, then `health`.

Generated 2026-10-20 04:28 UTC from `data/ipfs_status.json` (7,943 CIDs checked) and `data/live_status.json`. 202 of 1,973 moments have at least one missing file.

| IPFS health | moments |
|---|---|
| all_ok | 1771 |
| some_missing | 131 |
| video_missing | 71 |
| all_missing | 0 |
| unchecked | 0 |

| Card | Player | Set | Rarity | Health | Missing on IPFS | CDN cover | CDN video | Listed now |
|---|---|---|---|---|---|---|---|---|
| 16 | Troy Terry | Base | Core | video_missing | video, card-image | yes | yes | yes |
| 18 | Marc-Andre Fleury | Base | Core | video_missing | video, thumbnail | yes | yes | yes |
| 19 | Cole Caufield | Base | Core | video_missing | video | yes | yes | yes |
| 20 | Dawson Mercer | Base | Core | video_missing | video, card-image, thumbnail | yes | yes | yes |
| 22 | Mark Stone | Base | Core | video_missing | video, cover, thumbnail | yes | yes | yes |
| 40 | Dylan Larkin | Base | Core | video_missing | video, thumbnail | yes | yes | yes |
| 42 | David Pastrnak | Base | Core | video_missing | video, thumbnail | yes | yes | yes |
| 63 | Jordan Eberle | Base | Core | video_missing | video, thumbnail | yes | yes | yes |
| 68 | Matty Beniers | Opening Ice | Rare | video_missing | video, card-image | yes | yes | yes |
| 70 | William Eklund | Opening Ice | Rare | video_missing | video, card-image, thumbnail | yes | yes | yes |
| 100 | Anze Kopitar | Opening Ice: Elites | Rare | video_missing | video, cover-16x9 | yes | yes | yes |
| 101 | Sidney Crosby | Opening Ice: Elites | Rare | video_missing | video, cover, thumbnail | yes | yes | yes |
| 107 | Adam Fox | Opening Ice: Elites | Rare | video_missing | video | yes | yes | yes |
| 112 | Alex Ovechkin | Making the Mark | Epic | video_missing | video | yes | yes | yes |
| 114 | Connor McDavid | Making the Mark | Epic | video_missing | video, cover-16x9 | yes | yes | yes |
| 120 | Claude Giroux | Making the Mark | Epic | video_missing | video | yes | yes | yes |
| 127 | Sergei Bobrovsky | The Hunt for Stanley 2023 | Limited | video_missing | video | yes | yes | yes |
| 131 | Phillip Di Giuseppe | Base 2023-24 | Core | video_missing | video | yes | yes | yes |
| 154 | Logan O'Connor | Base 2023-24 | Core | video_missing | video | yes | yes | yes |
| 166 | Filip Hronek | Base 2023-24 | Core | video_missing | video | yes | yes | yes |
| 185 | Travis Sanheim | Base 2023-24 | Core | video_missing | video, cover, thumbnail | yes | yes | yes |
| 213 | Connor Bedard | Opening Ice 2023-24 | Rare | video_missing | video, cover, cover-16x9 | yes | yes | yes |
| 218 | Simon Nemec | Opening Ice 2023-24 | Rare | video_missing | video, card-image, cover-16x9 | yes | yes | yes |
| 233 | Patrick Roy | Cause for a Celly: 90s | Epic | video_missing | video, cover-16x9 | yes | yes | yes |
| 237 | Mario Lemieux | Cause for a Celly: 90s | Epic | video_missing | video, cover-16x9 | yes | yes | yes |
| 244 | Alexandar Georgiev | Guardians of the Net | Limited | video_missing | video, cover, card-image, cover-16x9 | yes | yes | yes |
| 245 | Jake Oettinger | Guardians of the Net | Limited | video_missing | video, card-image | yes | yes | yes |
| 254 | Charlie Lindgren | Guardians of the Net | Limited | video_missing | video | yes | yes | yes |
| 262 | Alex Ovechkin | The Greatest Achievements | Legendary | video_missing | video | yes | yes | yes |
| 270 | Peyton Krebs | Stadiums & Skylines | Core | video_missing | video, card-image | yes | yes | yes |
| 271 | Mike Condon | Stadiums & Skylines | Core | video_missing | video | yes | yes | yes |
| 285 | Tyler Toffoli | Stadiums & Skylines | Core | video_missing | video | yes | yes | yes |
| 290 | Jake Sanderson | Next-Gen Class | Limited | video_missing | video | yes | yes | yes |
| 294 | Evan Bouchard | Next-Gen Class | Limited | video_missing | video | yes | yes | yes |
| 296 | Aliaksei Protas | Next-Gen Class | Limited | video_missing | video, cover-16x9 | yes | yes | yes |
| 305 | Trevor Zegras | Next-Gen Class | Limited | video_missing | video | yes | yes | yes |
| 306 | K'Andre Miller | Next-Gen Class | Limited | video_missing | video, cover | yes | yes | yes |
| 426 | Jared McCann | Signature Fandoms | Heroic | video_missing | video | yes | yes | yes |
| 528 | Alexis Lafrenière | Signature Cores | Heroic | video_missing | video | yes | yes | yes |
| 549 | Nico Hischier | Signature Cores | Heroic | video_missing | video | yes | yes | yes |
| 575 | Matthew Phillips | Signature Cores | Heroic | video_missing | video | yes | yes | yes |
| 583 | Peyton Krebs | Signature Cores | Heroic | video_missing | video | yes | yes | yes |
| 601 | Connor Hellebuyck | Signature Limiteds | Heroic | video_missing | video | yes | yes | yes |
| 615 | Seth Jarvis | Signature Limiteds | Heroic | video_missing | video | yes | yes | yes |
| 648 | Mark Stone | Signature Limiteds | Heroic | video_missing | video | yes | yes | yes |
| 649 | Chris Chelios | Signature Limiteds | Heroic | video_missing | video | yes | yes | yes |
| 650 | Elvis Merzlikins | Signature Limiteds | Heroic | video_missing | video | yes | yes | yes |
| 657 | Luc Robitaille | Signature Limiteds | Heroic | video_missing | video | yes | yes | yes |
| 669 | Joe Sakic | Signature Limiteds | Heroic | video_missing | video | yes | yes | yes |
| 721 | Sebastian Aho | Signature Rares | Heroic | video_missing | video | yes | yes | yes |
| 729 | Simon Nemec | Signature Rares | Heroic | video_missing | video | yes | yes | yes |
| 732 | Auston Matthews | Signature Rares | Heroic | video_missing | video | yes | yes | yes |
| 733 | Kirill Kaprizov | Signature Rares | Heroic | video_missing | video | yes | yes | yes |
| 763 | Mario Lemieux | Signature Epics | Heroic | video_missing | video | yes | yes | yes |
| 787 | Jesper Wallstedt | Signature Rares | Heroic | video_missing | video | yes | yes | yes |
| 792 | Lucas Raymond | Signature Rares | Heroic | video_missing | video | yes | yes | yes |
| 795 | Dylan Larkin | Signature Rares | Heroic | video_missing | video | yes | yes | yes |
| 796 | Chris Pronger | Signature Rares | Heroic | video_missing | video | yes | yes | yes |
| 1114 | Alex Ovechkin | Set the Tone | Limited | video_missing | video, cover, card-image, cover-16x9 | yes | yes | yes |
| 1115 | Brayden Schenn | Set the Tone | Limited | video_missing | video, cover, card-image, cover-16x9 | yes | yes | yes |
| 1116 | Charlie McAvoy | Set the Tone | Limited | video_missing | video, cover, card-image, cover-16x9 | yes | yes | yes |
| 1117 | Brooks Orpik | Set the Tone | Limited | video_missing | video, cover, card-image, cover-16x9 | yes | yes | yes |
| 1118 | Cal Clutterbuck | Set the Tone | Limited | video_missing | video, cover, card-image, cover-16x9 | yes | yes | yes |
| 1153 | Lukas Dostal | Ice Nation | Fandom | video_missing | video | yes | yes | yes |
| 1158 | Rasmus Andersson | Ice Nation | Fandom | video_missing | video | yes | yes | yes |
| 1159 | Carter Verhaeghe | Ice Nation | Fandom | video_missing | video, card-image | yes | yes | yes |
| 1160 | Jake Walman | Ice Nation | Fandom | video_missing | video, cover, card-image, cover-16x9 | yes | yes | yes |
| 1161 | William Karlsson | Ice Nation | Fandom | video_missing | video, cover, card-image, thumbnail | yes | yes | yes |
| 1162 | Juuso Parssinen | Ice Nation | Fandom | video_missing | video, cover, card-image, cover-16x9 | yes | yes | yes |
| 1163 | Nick Suzuki | Ice Nation | Fandom | video_missing | video, cover, card-image, cover-16x9 | yes | yes | yes |
| 1177 | Andreas Athanasiou | Ice Nation | Fandom | video_missing | video, cover, cover-16x9 | yes | yes | yes |
| 21 | Linus Ullmark | Base | Core | some_missing | cover-16x9 | yes | yes | yes |
| 24 | Rasmus Dahlin | Base | Core | some_missing | thumbnail | yes | yes | yes |
| 26 | Mikko Rantanen | Base | Core | some_missing | card-image, thumbnail | yes | yes | yes |
| 27 | Artemi Panarin | Base | Core | some_missing | cover, cover-16x9, thumbnail | yes | yes | yes |
| 29 | Travis Konecny | Base | Core | some_missing | thumbnail | yes | yes | yes |
| 31 | Evgeny Kuznetsov | Base | Core | some_missing | card-image, thumbnail | yes | yes | yes |
| 35 | Evgeni Malkin | Base | Core | some_missing | thumbnail | yes | yes | yes |
| 36 | Juuse Saros | Base | Core | some_missing | card-image, thumbnail | yes | yes | yes |
| 38 | Aleksander Barkov | Base | Core | some_missing | cover-16x9, thumbnail | yes | yes | yes |
| 44 | Tage Thompson | Base | Core | some_missing | thumbnail | yes | yes | yes |
| 45 | Jason Robertson | Base | Core | some_missing | thumbnail | yes | yes | yes |
| 46 | Leon Draisaitl | Base | Core | some_missing | thumbnail | yes | yes | yes |
| 48 | Cale Makar | Base | Core | some_missing | thumbnail | yes | yes | yes |
| 49 | Jack Hughes | Base | Core | some_missing | thumbnail | yes | yes | yes |
| 51 | Kirill Kaprizov | Base | Core | some_missing | thumbnail | yes | yes | yes |
| 53 | Sidney Crosby | Base | Core | some_missing | cover, cover-16x9, thumbnail | yes | yes | yes |
| 56 | Elias Pettersson | Base | Core | some_missing | thumbnail | yes | yes | yes |
| 58 | Johnny Gaudreau | Base | Core | some_missing | cover, thumbnail | yes | yes | yes |
| 62 | Tim Stützle | Base | Core | some_missing | thumbnail | yes | yes | yes |
| 64 | Sebastian Aho | Base | Core | some_missing | thumbnail | yes | yes | yes |
| 65 | Jack Eichel | Base | Core | some_missing | card-image, thumbnail | yes | yes | yes |
| 66 | Trevor Zegras | Base | Core | some_missing | thumbnail | yes | yes | yes |
| 67 | Jake Sanderson | Opening Ice | Rare | some_missing | thumbnail | yes | yes | yes |
| 69 | Mason McTavish | Opening Ice | Rare | some_missing | cover-16x9, thumbnail | yes | yes | yes |
| 71 | Jake Neighbours | Opening Ice | Rare | some_missing | thumbnail | yes | yes | yes |
| 88 | Auston Matthews | Opening Ice: Elites | Rare | some_missing | thumbnail | yes | yes | yes |
| 92 | Cale Makar | Opening Ice: Elites | Rare | some_missing | thumbnail | yes | yes | yes |
| 93 | Elias Pettersson | Opening Ice: Elites | Rare | some_missing | thumbnail | yes | yes | yes |
| 94 | Nikita Kucherov | Opening Ice: Elites | Rare | some_missing | card-image, thumbnail | yes | yes | yes |
| 95 | Jack Eichel | Opening Ice: Elites | Rare | some_missing | thumbnail | yes | yes | yes |
| 96 | Leon Draisaitl | Opening Ice: Elites | Rare | some_missing | cover-16x9, thumbnail | yes | yes | yes |
| 97 | Nathan MacKinnon | Opening Ice: Elites | Rare | some_missing | cover-16x9 | yes | yes | yes |
| 98 | Tage Thompson | Opening Ice: Elites | Rare | some_missing | card-image | yes | yes | yes |
| 102 | Sebastian Aho | Opening Ice: Elites | Rare | some_missing | card-image, thumbnail | yes | yes | yes |
| 103 | Mitch Marner | Opening Ice: Elites | Rare | some_missing | card-image, cover-16x9, thumbnail | yes | yes | yes |
| 104 | Kirill Kaprizov | Opening Ice: Elites | Rare | some_missing | thumbnail | yes | yes | yes |
| 106 | Victor Hedman | Opening Ice: Elites | Rare | some_missing | thumbnail | yes | yes | yes |
| 108 | David Pastrnak | Opening Ice: Elites | Rare | some_missing | cover, cover-16x9, thumbnail | yes | yes | yes |
| 109 | Charlie McAvoy | Opening Ice: Elites | Rare | some_missing | card-image | yes | yes | yes |
| 111 | Connor McDavid | Opening Ice: Elites | Rare | some_missing | cover, card-image, thumbnail | yes | yes | yes |
| 113 | Patrice Bergeron | Making the Mark | Epic | some_missing | thumbnail | yes | yes | yes |
| 115 | Linus Ullmark | Making the Mark | Epic | some_missing | cover, card-image | yes | yes | yes |
| 118 | Joe Pavelski | Making the Mark | Epic | some_missing | card-image | yes | yes | yes |
| 121 | Mark Stone | The Hunt for Stanley 2023 | Limited | some_missing | cover, thumbnail | yes | yes | yes |
| 122 | Aleksander Barkov | The Hunt for Stanley 2023 | Limited | some_missing | cover-16x9 | yes | yes | yes |
| 123 | John Tavares | The Hunt for Stanley 2023 | Limited | some_missing | cover, thumbnail | yes | yes | yes |
| 126 | Adin Hill | The Hunt for Stanley 2023 | Limited | some_missing | cover, thumbnail | yes | yes | yes |
| 128 | Oliver Bjorkstrand | The Hunt for Stanley 2023 | Limited | some_missing | cover, thumbnail | yes | yes | yes |
| 129 | Matthew Tkachuk | The Hunt for Stanley 2023 | Limited | some_missing | thumbnail | yes | yes | yes |
| 130 | Jack Eichel | The Hunt for Stanley 2023 | Limited | some_missing | thumbnail | yes | yes | yes |
| 132 | Mike Matheson | Base 2023-24 | Core | some_missing | thumbnail | yes | yes | yes |
| 133 | Matthew Phillips | Base 2023-24 | Core | some_missing | thumbnail | yes | yes | yes |
| 135 | Tom Wilson | Base 2023-24 | Core | some_missing | cover-16x9, thumbnail | yes | yes | yes |
| 136 | Mark Scheifele | Base 2023-24 | Core | some_missing | thumbnail | yes | yes | yes |
| 137 | Zemgus Girgensons | Base 2023-24 | Core | some_missing | card-image, thumbnail | yes | yes | yes |
| 138 | Ryan Hartman | Base 2023-24 | Core | some_missing | thumbnail | yes | yes | yes |
| 139 | Mika Zibanejad | Base 2023-24 | Core | some_missing | cover | yes | yes | yes |
| 140 | Corey Perry | Base 2023-24 | Core | some_missing | card-image, thumbnail | yes | yes | yes |
| 141 | Luke Evangelista | Base 2023-24 | Core | some_missing | card-image | yes | yes | yes |
| 142 | Martin Necas | Base 2023-24 | Core | some_missing | card-image | yes | yes | yes |
| 143 | Michael Bunting | Base 2023-24 | Core | some_missing | thumbnail | yes | yes | yes |
| 145 | Sam Lafferty | Base 2023-24 | Core | some_missing | card-image, cover-16x9, thumbnail | yes | yes | yes |
| 146 | Logan Thompson | Base 2023-24 | Core | some_missing | cover | yes | yes | yes |
| 147 | Paul Cotter | Base 2023-24 | Core | some_missing | cover | yes | yes | yes |
| 148 | Vladimir Tarasenko | Base 2023-24 | Core | some_missing | card-image | yes | yes | yes |
| 152 | Colton Sissons | Base 2023-24 | Core | some_missing | thumbnail | yes | yes | yes |
| 155 | Adam Lowry | Base 2023-24 | Core | some_missing | thumbnail | yes | yes | yes |
| 156 | Connor Bedard | Base 2023-24 | Core | some_missing | cover-16x9 | yes | yes | yes |
| 159 | Robert Thomas | Base 2023-24 | Core | some_missing | thumbnail | yes | yes | yes |
| 160 | Filip Zadina | Base 2023-24 | Core | some_missing | thumbnail | yes | yes | yes |
| 162 | Tyler Seguin | Base 2023-24 | Core | some_missing | card-image | yes | yes | yes |
| 163 | Pavel Mintyukov | Base 2023-24 | Core | some_missing | cover, thumbnail | yes | yes | yes |
| 165 | J.T. Miller | Base 2023-24 | Core | some_missing | cover, card-image, thumbnail | yes | yes | yes |
| 168 | Blake Coleman | Base 2023-24 | Core | some_missing | card-image | yes | yes | yes |
| 170 | Clayton Keller | Base 2023-24 | Core | some_missing | thumbnail | yes | yes | yes |
| 171 | Adam Fantilli | Base 2023-24 | Core | some_missing | cover | yes | yes | yes |
| 174 | Oliver Wahlstrom | Base 2023-24 | Core | some_missing | card-image | yes | yes | yes |
| 178 | Jesper Bratt | Base 2023-24 | Core | some_missing | thumbnail | yes | yes | yes |
| 179 | Sean Durzi | Base 2023-24 | Core | some_missing | cover | yes | yes | yes |
| 180 | Alexis Lafrenière | Base 2023-24 | Core | some_missing | thumbnail | yes | yes | yes |
| 181 | Matt Duchene | Base 2023-24 | Core | some_missing | thumbnail | yes | yes | yes |
| 182 | Trevor Moore | Base 2023-24 | Core | some_missing | thumbnail | yes | yes | yes |
| 184 | Jacob Trouba | Base 2023-24 | Core | some_missing | thumbnail | yes | yes | yes |
| 201 | Will Cuylle | Opening Ice 2023-24 | Rare | some_missing | thumbnail | yes | yes | yes |
| 202 | John Beecher | Opening Ice 2023-24 | Rare | some_missing | thumbnail | yes | yes | yes |
| 203 | Matt Coronato | Opening Ice 2023-24 | Rare | some_missing | thumbnail | yes | yes | yes |
| 204 | Connor Zary | Opening Ice 2023-24 | Rare | some_missing | thumbnail | yes | yes | yes |
| 206 | Brock Faber | Opening Ice 2023-24 | Rare | some_missing | thumbnail | yes | yes | yes |
| 208 | Thomas Bordeleau | Opening Ice 2023-24 | Rare | some_missing | card-image, thumbnail | yes | yes | yes |
| 210 | David Jiricek | Opening Ice 2023-24 | Rare | some_missing | cover-16x9 | yes | yes | yes |
| 211 | Logan Cooley | Opening Ice 2023-24 | Rare | some_missing | card-image, thumbnail | yes | yes | yes |
| 214 | Pavel Mintyukov | Opening Ice 2023-24 | Rare | some_missing | thumbnail | yes | yes | yes |
| 219 | Egor Zamula | Opening Ice 2023-24 | Rare | some_missing | cover | yes | yes | yes |
| 229 | Scott Niedermayer | Cause for a Celly: 90s | Epic | some_missing | cover | yes | yes | yes |
| 230 | Jari Kurri | Cause for a Celly: 90s | Epic | some_missing | cover-16x9 | yes | yes | yes |
| 234 | Wayne Gretzky | Cause for a Celly: 90s | Epic | some_missing | cover-16x9 | yes | yes | yes |
| 235 | Peter Forsberg | Cause for a Celly: 90s | Epic | some_missing | cover | yes | yes | yes |
| 236 | Mike Modano | Cause for a Celly: 90s | Epic | some_missing | cover, card-image | yes | yes | yes |
| 248 | Thatcher Demko | Guardians of the Net | Limited | some_missing | cover-16x9 | yes | yes | yes |
| 251 | Jeremy Swayman | Guardians of the Net | Limited | some_missing | cover-16x9 | yes | yes | yes |
| 252 | Marc-Andre Fleury | Guardians of the Net | Limited | some_missing | cover | yes | yes | yes |
| 256 | Jacob Markstrom | Guardians of the Net | Limited | some_missing | card-image | yes | yes | yes |
| 260 | Ray Bourque | The Greatest Achievements | Legendary | some_missing | cover-16x9 | yes | yes | yes |
| 261 | Teemu Selanne | The Greatest Achievements | Legendary | some_missing | cover | yes | yes | yes |
| 265 | Chris Chelios | Hometown History: Chicago Blackhawks (L) | Limited | some_missing | card-image, cover-16x9 | yes | yes | yes |
| 273 | Bryan Little | Stadiums & Skylines | Core | some_missing | cover | yes | yes | yes |
| 276 | Derek Stepan | Stadiums & Skylines | Core | some_missing | card-image | yes | yes | yes |
| 279 | Troy Brouwer | Stadiums & Skylines | Core | some_missing | card-image | yes | yes | yes |
| 280 | Tyler Bozak | Stadiums & Skylines | Core | some_missing | cover-16x9 | yes | yes | yes |
| 282 | Gustav Nyquist | Stadiums & Skylines | Core | some_missing | cover-16x9 | yes | yes | yes |
| 284 | Auston Matthews | Stadiums & Skylines | Core | some_missing | cover | yes | yes | yes |
| 289 | Noah Dobson | Next-Gen Class | Limited | some_missing | cover-16x9 | yes | yes | yes |
| 291 | Matias Maccelli | Next-Gen Class | Limited | some_missing | cover | yes | yes | yes |
| 292 | Tim Stützle | Next-Gen Class | Limited | some_missing | cover-16x9 | yes | yes | yes |
| 300 | Bowen Byram | Next-Gen Class | Limited | some_missing | card-image, cover-16x9 | yes | yes | yes |
| 301 | Jake Neighbours | Next-Gen Class | Limited | some_missing | card-image | yes | yes | yes |
| 1152 | Matias Maccelli | Ice Nation | Fandom | some_missing | cover-16x9 | yes | yes | yes |
| 1157 | Andrei Svechnikov | Ice Nation | Fandom | some_missing | card-image | yes | yes | yes |
| 1164 | Evander Kane | Ice Nation | Fandom | some_missing | cover | yes | yes | yes |
| 1165 | Andrei Kuzmenko | Ice Nation | Fandom | some_missing | card-image | yes | yes | yes |
| 1171 | Andrei Vasilevskiy | Ice Nation | Fandom | some_missing | cover, cover-16x9 | yes | yes | yes |
| 1174 | Josh Morrissey | Ice Nation | Fandom | some_missing | cover-16x9 | yes | yes | yes |
| 1175 | Morgan Frost | Ice Nation | Fandom | some_missing | card-image | yes | yes | yes |
| 1176 | Noah Dobson | Ice Nation | Fandom | some_missing | cover | yes | yes | yes |
| 1178 | Jared McCann | Ice Nation | Fandom | some_missing | card-image | yes | yes | yes |
| 1179 | Bryan Rust | Ice Nation | Fandom | some_missing | cover | yes | yes | yes |
| 1180 | Kevin Fiala | Ice Nation | Fandom | some_missing | cover-16x9 | yes | yes | yes |
| 1181 | Vitek Vanecek | Ice Nation | Fandom | some_missing | cover, card-image | yes | yes | yes |
| 1182 | Adam Fox | Ice Nation | Fandom | some_missing | cover-16x9 | yes | yes | yes |
| 1183 | Bowen Byram | Ice Nation | Fandom | some_missing | cover, card-image, cover-16x9 | yes | yes | yes |
| 1496 | Rick Tocchet | Heart & Soul: 80s + 90s | Core | some_missing | cover, cover-16x9 | yes | yes | yes |

# GXBRIEL SMART SUB

Автоматическая сборка подписки для Karing на основе [Free-Nodes](https://github.com/735754647/Free-Nodes).

Проект сохраняет upstream-подход к загрузке, поддерживаемым протоколам, дедупликации и тестированию через Mihomo. Workflow запускается вручную и каждый час, выполняет реальный скачивающий speed test с порогом 24 Mbps (3 MB/s) и публикует не более 200 узлов в существующий Secret Gist `subscription.txt`.

Скорость измеряется из GitHub-hosted runner и не является гарантией скорости из России. При ошибке сборки или пустом результате публикация в Gist не выполняется, поэтому последний рабочий список сохраняется.

## Attribution and license

Код в `src/subbench`, `tests` и `scripts/install_mihomo.py` перенесён из проекта [735754647/Free-Nodes](https://github.com/735754647/Free-Nodes), автор — Hsin-chang He. Он распространяется по MIT License; исходный текст лицензии сохранён в [`LICENSE`](LICENSE).

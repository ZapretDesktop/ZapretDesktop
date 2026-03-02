from PyQt6.QtWidgets import (
    QLabel,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QMessageBox,
    QFileDialog,
)
from PyQt6.QtCore import Qt

from src.ui.standard_dialog import StandardDialog
from src.dialogs.vs_update_dialog import VSUpdateDialog
from src.core.translator import tr
from src.core.config_manager import ConfigManager
from src.core.path_utils import get_winws_path
from src.core.embedded_assets import get_app_icon

import os


class WinwsSetupDialog(StandardDialog):
    """Диалог, отображаемый при отсутствии папки winws."""

    def __init__(self, parent=None, config: ConfigManager | None = None):
        self.config = config or ConfigManager()
        settings = self.config.load_settings()
        lang = settings.get("language", "ru")

        super().__init__(
            parent=parent,
            title=tr("winws_setup_title", lang),
            width=520,
            height=260,
            icon=get_app_icon(),
            theme="dark",
        )

        self.lang = lang
        self._skipped = False

        layout = self.getContentLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        message = QLabel(tr("winws_setup_message", self.lang))
        message.setWordWrap(True)
        message.setStyleSheet("color: #D4D4D4; font-size: 13px;")
        layout.addWidget(message)

        path_label = QLabel(tr("winws_setup_path_label", self.lang))
        layout.addWidget(path_label)

        path_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(
            tr("winws_setup_path_placeholder", self.lang)
        )
        path_row.addWidget(self.path_edit)
        layout.addLayout(path_row)

        link_label = QLabel(tr("winws_setup_link_label", self.lang))
        layout.addWidget(link_label)

        self.link_edit = QLineEdit()
        repo_setting = ""
        try:
            repo_setting = (
                self.config.get_setting("zapret_repo", "") or ""
            ).strip()
        except Exception:
            repo_setting = ""
        if not repo_setting:
            default_link = "https://github.com/Flowseal/zapret-discord-youtube"
        else:
            if "github.com" in repo_setting.lower():
                default_link = repo_setting
            else:
                default_link = f"https://github.com/{repo_setting}"
        self.link_edit.setText(default_link)
        layout.addWidget(self.link_edit)

        layout.addStretch()

        buttons_row = QHBoxLayout()
        buttons_row.addStretch()

        self.download_btn = QPushButton(tr("winws_setup_download", self.lang))
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_btn.clicked.connect(self._on_download_clicked)
        buttons_row.addWidget(self.download_btn)

        self.choose_btn = QPushButton(tr("winws_setup_choose", self.lang))
        self.choose_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.choose_btn.clicked.connect(self._on_choose_clicked)
        buttons_row.addWidget(self.choose_btn)

        self.cancel_btn = QPushButton(tr("winws_setup_cancel", self.lang))
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)
        buttons_row.addWidget(self.cancel_btn)

        self.skip_btn = QPushButton(tr("winws_setup_skip", self.lang))
        self.skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skip_btn.clicked.connect(self._on_skip_clicked)
        buttons_row.addWidget(self.skip_btn)

        layout.addLayout(buttons_row)

    def _show_error(self, text: str):
        QMessageBox.critical(self, tr("msg_error", self.lang), text)

    @property
    def skipped(self) -> bool:
        return self._skipped

    def _on_choose_clicked(self):
        path = self.path_edit.text().strip()

        if not path:
            folder = QFileDialog.getExistingDirectory(
                self,
                tr("winws_setup_select_folder", self.lang),
            )
            if not folder:
                return
            path = folder
            self.path_edit.setText(folder)

        path = os.path.abspath(path)

        if os.path.isdir(path):
            winws_exe = os.path.join(path, "bin", "winws.exe")
            if not os.path.isfile(winws_exe):
                self._show_error(tr("winws_setup_invalid_folder", self.lang))
                return
            try:
                self.config.set_setting("winws_path", path)
            except Exception:
                pass
            self.accept()
            return

        if os.path.isfile(path) and path.lower().endswith(".zip"):
            try:
                from src.core.zapret_updater import ZapretUpdater

                updater = ZapretUpdater()
                updater.extract_zip_to_winws(path)
                winws_folder = get_winws_path()
                try:
                    self.config.set_setting("winws_path", winws_folder)
                except Exception:
                    pass
                self.accept()
            except Exception as e:
                self._show_error(
                    tr("winws_setup_extract_error", self.lang).format(str(e))
                )
            return

        self._show_error(tr("winws_setup_invalid_path", self.lang))

    def _on_download_clicked(self):
        from PyQt6.QtWidgets import QApplication
        from src.core.zapret_updater import ZapretUpdater

        repo = (self.link_edit.text() or "").strip()
        if not repo:
            repo = "https://github.com/Flowseal/zapret-discord-youtube"

        try:
            self.config.set_setting("zapret_repo", repo)
        except Exception:
            pass

        lang = self.lang

        update_dialog = VSUpdateDialog(self, language=lang)
        update_dialog.set_status(tr("update_checking", lang))
        update_dialog.show_cancel(False)
        update_dialog.show()
        QApplication.processEvents()

        try:
            updater = ZapretUpdater()
            info = updater.check_for_updates()
            if "error" in info:
                raise Exception(info["error"])

            download_url = info.get("download_url")
            if not download_url:
                raise Exception(tr("winws_setup_no_download", lang))

            latest_version = info.get("latest_version") or "unknown"

            def progress_cb(value: float):
                update_dialog.set_progress(value)
                QApplication.processEvents()

            update_dialog.set_status(tr("update_downloading", lang))
            zip_path = updater.download_update(download_url, progress_callback=progress_cb)

            update_dialog.set_status(tr("update_installing", lang))
            update_dialog.set_progress(90)
            QApplication.processEvents()

            updater.extract_and_update(zip_path, latest_version)

            # После установки применяем те же автоматические правки стратегий,
            # что и при обновлении через главное окно.
            try:
                settings = self.config.load_settings()
            except Exception:
                settings = {}

            winws_folder = get_winws_path()

            # Авто-добавление /B
            if settings.get("add_b_flag_on_update", False) and os.path.isdir(winws_folder):
                try:
                    bat_files = [
                        f for f in os.listdir(winws_folder)
                        if f.lower().endswith(".bat")
                        and os.path.isfile(os.path.join(winws_folder, f))
                    ]
                    old_string = 'start "zapret: %~n0" /min'
                    new_string = 'start "zapret: %~n0" /B /min'
                    for filename in bat_files:
                        file_path = os.path.join(winws_folder, filename)
                        try:
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                            if old_string in content:
                                new_content = content.replace(old_string, new_string)
                                with open(file_path, "w", encoding="utf-8") as f:
                                    f.write(new_content)
                        except Exception:
                            continue
                except Exception:
                    pass

            # Авто-удаление check_updates
            if settings.get("remove_check_updates", False) and os.path.isdir(winws_folder):
                try:
                    bat_files = [
                        f for f in os.listdir(winws_folder)
                        if f.lower().endswith(".bat")
                        and os.path.isfile(os.path.join(winws_folder, f))
                    ]
                    for filename in bat_files:
                        file_path = os.path.join(winws_folder, filename)
                        try:
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                lines = f.readlines()
                            new_lines = []
                            modified = False
                            for line in lines:
                                stripped = line.strip().lower()
                                if (
                                    stripped == "call service.bat check_updates"
                                    or "call service.bat check_updates" in stripped
                                ):
                                    modified = True
                                    continue
                                new_lines.append(line)
                            if modified:
                                with open(file_path, "w", encoding="utf-8") as f:
                                    f.writelines(new_lines)
                        except Exception:
                            continue
                except Exception:
                    pass

            update_dialog.set_progress(100)
            update_dialog.set_status(tr("update_completed", lang))
            QApplication.processEvents()

            winws_folder = get_winws_path()
            try:
                self.config.set_setting("winws_path", winws_folder)
            except Exception:
                pass

            update_dialog.close()
            self.accept()
        except Exception as e:
            update_dialog.close()
            self._show_error(
                tr("winws_setup_download_error", lang).format(str(e))
            )

    def _on_skip_clicked(self):
        self._skipped = True
        self.accept()


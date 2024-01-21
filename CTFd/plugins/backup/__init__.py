import json
import shutil
import sys
import logging
import os
import tempfile
import zipfile
from datetime import datetime
from functools import wraps
from io import BytesIO
import schedule
import pytz

import dataset
from flask_apscheduler import APScheduler
from flask_restx import Namespace

from CTFd.plugins import (
    register_plugin_assets_directory,
    register_admin_plugin_menu_bar,
)
from CTFd.utils import get_config, set_config, get_app_config, current_backend_time
from flask import request, render_template, Blueprint, send_file

from ...api import CTFd_API_v1
from ...cache import cache
from ...utils.config import ctf_name
from ...utils.decorators import admins_only
from ...utils.exports import freeze_export
from ...utils.logging import log
from ...utils.migrations import get_current_revision
from ...utils.uploads import get_uploader

logger = logging.getLogger('backup')


def config(app):
    if not get_config("backup:setup"):
        for key, val in {
            'enabled': 'false',
            'interval': '7',
            'time': '3',
            'max': '8',
            'setup': 'true'
        }.items():
            set_config('backup:' + key, val)


interval = 7
time = 3


def load(app):
    config(app)
    plugin_name = __name__.split('.')[-1]

    global interval, time
    interval = get_config("backup:interval")
    time = get_config("backup:time")

    register_plugin_assets_directory(
        app,
        base_path=f"/plugins/{plugin_name}/assets",
        endpoint='plugins.backup.assets')
    register_admin_plugin_menu_bar(title='Backup',
                                   route='/plugins/backup/admin/settings')

    page_blueprint = Blueprint("backup",
                               __name__,
                               template_folder="templates",
                               static_folder="static",
                               url_prefix="/plugins/backup")
    CTFd_API_v1.add_namespace(Namespace("backup-admin"),
                              path="/plugins/backup/admin")

    def format_size(size):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                break
            size /= 1024.0
        return "{:.2f} {}".format(size, unit)

    @page_blueprint.route('/admin/settings')
    @admins_only
    def admin_list_configs():
        global interval, time
        if get_config("backup:interval") is not interval or get_config("backup:time") is not time:
            interval = get_config("backup:interval")
            time = get_config("backup:time")
            print("[Auto Backup] Configuration updated, tasks rescheduled.", flush=True)
            update_schedule(interval, time)

        upload_folder = os.path.join(
            os.path.normpath(app.root_path), app.config.get("UPLOAD_FOLDER")
        )
        auto_backups_folder = os.path.join(upload_folder, "autoBackups")
        os.makedirs(auto_backups_folder, exist_ok=True)
        backup_files = []
        for root, dirs, files in os.walk(auto_backups_folder):
            for file in files:
                file_path = os.path.join(root, file)
                file_size = os.path.getsize(file_path)
                file_date = os.path.getctime(file_path)
                backup_files.append({
                    'name': file,
                    'size': format_size(file_size),
                    'date': datetime.utcfromtimestamp(file_date)
                })
        return render_template('backup_config.html', backup_files=backup_files)

    @page_blueprint.route("/admin/download")
    @admins_only
    def admin_download_backup():
        upload_folder = os.path.join(
            os.path.normpath(app.root_path), app.config.get("UPLOAD_FOLDER")
        )
        auto_backups_folder = os.path.join(upload_folder, "autoBackups")
        os.makedirs(auto_backups_folder, exist_ok=True)

        backup_name = request.args.get("name")
        backup_path = os.path.join(auto_backups_folder, backup_name)

        if os.path.exists(backup_path):
            return send_file(
                backup_path,
                as_attachment=True
            )
        else:
            return "File not found", 404

    @page_blueprint.route("/admin/delete")
    @admins_only
    def admin_delete_backup():
        upload_folder = os.path.join(
            os.path.normpath(app.root_path), app.config.get("UPLOAD_FOLDER")
        )
        auto_backups_folder = os.path.join(upload_folder, "autoBackups")
        os.makedirs(auto_backups_folder, exist_ok=True)

        backup_name = request.args.get("name")
        backup_path = os.path.join(auto_backups_folder, backup_name)
        if os.path.exists(backup_path):
            os.remove(backup_path)
            return {
                'success': True,
                'message': 'Deleted!'
            }, 200
        else:
            return {
                'success': False,
                'message': 'File not found!'
            }, 200

    log_dir = app.config.get('LOG_FOLDER', os.path.join(os.path.dirname(__file__), 'logs'))
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file = os.path.join(log_dir, 'backup.log')

    if not os.path.exists(log_file):
        open(log_file, 'a').close()
    logger.addHandler(logging.handlers.RotatingFileHandler(log_file, maxBytes=10000))
    logger.addHandler(logging.StreamHandler(stream=sys.stdout))
    logger.propagate = 0

    def custom_export_ctf():
        db = dataset.connect(get_app_config("SQLALCHEMY_DATABASE_URI"))
        backup = tempfile.NamedTemporaryFile()
        backup_zip = zipfile.ZipFile(backup, "w")
        tables = db.tables
        for table in tables:
            result = db[table].all()
            result_file = BytesIO()
            freeze_export(result, fileobj=result_file)
            result_file.seek(0)
            backup_zip.writestr("db/{}.json".format(table), result_file.read())
        if "alembic_version" not in tables:
            result = {
                "count": 1,
                "results": [{"version_num": get_current_revision()}],
                "meta": {},
            }
            result_file = BytesIO()
            json.dump(result, result_file)
            result_file.seek(0)
            backup_zip.writestr("db/alembic_version.json", result_file.read())
        uploader = get_uploader()
        uploader.sync()
        upload_folder = os.path.join(
            os.path.normpath(app.root_path), app.config.get("UPLOAD_FOLDER")
        )
        for root, _dirs, files in os.walk(upload_folder):
            for file in files:
                parent_dir = os.path.basename(root)
                if not "autoBackups" in parent_dir:
                    backup_zip.write(
                        os.path.join(root, file),
                        arcname=os.path.join("uploads", parent_dir, file),
                    )

        backup_zip.close()
        backup.seek(0)
        return backup

    def delete_oldest_file(folder_path):
        files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]

        if len(files) > get_config("backup:max"):
            files = sorted(files, key=lambda x: os.path.getmtime(os.path.join(folder_path, x)))

            file_to_delete = os.path.join(folder_path, files[0])
            os.remove(file_to_delete)
            print(f"[Auto Backup] Oldest backup deleted! {file_to_delete}", flush=True)

    def write_backup():
        backup_file = custom_export_ctf()

        upload_folder = os.path.join(
            os.path.normpath(app.root_path), app.config.get("UPLOAD_FOLDER")
        )
        auto_backups_folder = os.path.join(upload_folder, "autoBackups")
        os.makedirs(auto_backups_folder, exist_ok=True)

        name = ctf_name()
        day = current_backend_time().strftime("%Y-%m-%d_%T")
        full_name = os.path.join(auto_backups_folder, f"{name}.{day}.zip")
        with open(full_name, "wb") as target:
            shutil.copyfileobj(backup_file, target)
        print(f"[Auto Backup] Backup: {name}.{day}.zip", flush=True)
        delete_oldest_file(auto_backups_folder)

    @page_blueprint.route("/admin/backupNow")
    @admins_only
    def admin_backup_now():
        write_backup()
        return {
            'success': True,
            'message': 'Backup Completed!'
        }, 200

    def single_task(task, t):
        def wrap(func):
            @wraps(func)
            def inner(*args, **kwargs):
                add_result = cache.get(key=task)
                if not add_result:
                    cache.set(key=task, value=True, timeout=t)
                    try:
                        result = func(*args, **kwargs)
                        return result
                    except Exception as e:
                        raise e
                else:
                    return

            return inner

        return wrap

    def convert_hours_to_time_string(hours):
        return f"{hours:02d}:00"

    @single_task("backup", 1800)
    def backup():
        with app.app_context():
            if get_config("backup:enabled"):
                write_backup()
                print("[Auto Backup] Automatic backup successful!", flush=True)
            else:
                print("[Auto Backup] Automatic backup error!", flush=True)

    def check():
        global interval, time
        with app.app_context():
            if get_config("backup:interval") is not interval or get_config("backup:time") is not time:
                interval = get_config("backup:interval")
                time = get_config("backup:time")
                print("[Auto Backup] Configuration updated, tasks rescheduled.", flush=True)
                update_schedule(interval, time)
            schedule.run_pending()

    def update_schedule(it, t):
        schedule.clear()
        schedule.every(it).days.at(convert_hours_to_time_string(t),
                                   pytz.timezone(get_config("backend_timezone", "Asia/Shanghai"))).do(backup)
        print("[Auto Backup] Schedule updated!", flush=True)
        print(f'[Auto Backup] Tasks incoming: {schedule.get_jobs()}', flush=True)

    scheduler = APScheduler()
    scheduler.init_app(app)
    scheduler.start()
    scheduler.add_job(id='auto-backup-check',
                      func=check,
                      trigger="interval",
                      seconds=10)

    schedule.every(interval).days.at(convert_hours_to_time_string(time),
                                     pytz.timezone(get_config("backend_timezone", "Asia/Shanghai"))).do(backup)
    print(f'[Auto Backup] Task incoming: {schedule.get_jobs()}', flush=True)

    app.register_blueprint(page_blueprint)

"""Optional non-destructive migration of local SQLite data from SINA Fresh 0.2.

Makes transactionally consistent copies using SQLite backup. Never edits the old DBs.
Never replaces existing target DBs. Stop both SINA processes before migrating.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parent
DB_NAMES = ('operator_feedback.sqlite3','live_measurements.sqlite3')


def migrate(old_root: Path, new_root: Path = ROOT) -> dict[str,str]:
    old_root, new_root = old_root.resolve(), new_root.resolve()
    if old_root == new_root:
        raise ValueError('Old and new folders must be different.')
    source_dir = old_root/'user_data'
    target_dir = new_root/'user_data'
    result={}
    for name in DB_NAMES:
        old=source_dir/name
        target=target_dir/name
        if not old.is_file():
            result[name]='not_found_in_old_version'
            continue
        if target.exists():
            raise FileExistsError(f'Target DB already exists: {target}. Migration refuses overwrite.')
        target_dir.mkdir(parents=True,exist_ok=True)
        temp=target.with_name(target.name+'.incoming')
        if temp.exists():
            raise FileExistsError(f'Incomplete previous migration file exists: {temp}')
        try:
            # Read-only old database, snapshot including committed WAL transactions.
            old_conn=sqlite3.connect(old.as_uri()+'?mode=ro',uri=True)
            try:
                new_conn=sqlite3.connect(str(temp))
                try:
                    old_conn.backup(new_conn)
                    integrity=new_conn.execute('PRAGMA integrity_check').fetchone()[0]
                    if integrity!='ok':
                        raise RuntimeError(f'Backup integrity check failed for {name}: {integrity}')
                finally:
                    new_conn.close()
            finally:
                old_conn.close()
            # Final target checked again. No intentional overwrite.
            if target.exists():
                raise FileExistsError(f'Target created during migration: {target}')
            temp.rename(target)
            result[name]='copied_and_integrity_checked'
        finally:
            if temp.exists():
                temp.unlink()
    return result


def main():
    parser=argparse.ArgumentParser(description='Optional SINA 0.2 SQLite data migration to 0.2.1')
    parser.add_argument('--from-dir',type=Path,required=True,help='Old SINA_FRESH_0_2 folder')
    parser.add_argument('--to-dir',type=Path,default=ROOT,help='New SINA_FRESH_0_2_1 folder')
    args=parser.parse_args()
    try:
        for name,status in migrate(args.from_dir,args.to_dir).items():
            print(f'{name}: {status}')
    except Exception as exc:
        parser.exit(1,f'Migration not completed: {exc}\n')

if __name__=='__main__':main()

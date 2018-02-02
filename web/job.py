import os
import shutil
import json
import sql_pool
import MySQLdb
import sys
import re
from user import User

class Job:
    __dbfields = ["user_id","name","error_message","status_id","creation_date","modified_date", "is_active"]
    __extfields = ["status", "role"]

    def __init__(self, job_id, meta=None):
        self.job_id = job_id
        map(lambda x: setattr(self, x, None), self.__dbfields + self.__extfields)
        self.root_path = "" 
        self.users = []
        self.meta = meta

    def get_adjusted_phenotypes(self):
        phe_file = self.relative_path("output.phe")
        phenos = {}
        if os.path.exists(phe_file):
            with open(phe_file) as f:
                for line in f:
                    (sample, val) = line.split()
                    phenos[sample] = float(val)
        return phenos

    def relative_path(self, *args):
        return os.path.expanduser(os.path.join(self.root_path, *args))

    def get_genotype_id(self):
        return self.meta.get("genotype", None) 

    def get_output_files(self):
        files = []
        def add_if_exists(rel_path, display_name, primary=False):
            file_path = self.relative_path(rel_path)
            if os.path.exists(file_path):
                files.append({"path": rel_path, "size": os.path.getsize(file_path), 
                    "name": display_name, "primary": primary})
        add_if_exists("output.epacts.gz", "Epacts Results", True)
        add_if_exists("results.txt.gz", "SAIGE Results", True)
        add_if_exists("output.filtered.001.gz", "Filtered Results (p-val<0.001)")
        return files

    def get_output_file_path(self):
        files = [x for x in self.get_output_files() if x.get("primary", False)]
        if len(files)==1:
            return self.relative_path(files[0]["path"])
        else:
            return None

    def as_object(self):
        obj = {key: getattr(self, key) for key in self.__dbfields  + self.__extfields if hasattr(self, key)} 
        obj["job_id"] = self.job_id
        obj["users"] = self.users
        obj["output_files"] = self.get_output_files()
        if self.meta:
            obj["details"] = self.meta
        return obj

    @staticmethod
    def get(job_id, config):
        if not re.match('[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}', job_id):
            return None
        job_folder = os.path.join(config.get("JOB_DATA_FOLDER", "./"), job_id)
        meta_path = os.path.expanduser(os.path.join(job_folder, "job.json"))
        if os.path.exists(meta_path):
            with open(meta_path) as meta_file:
                meta = json.load(meta_file)
        else:
           meta = dict()
        j = Job(job_id, meta)
        j.root_path = job_folder
        db = sql_pool.get_conn()
        cur = db.cursor(MySQLdb.cursors.DictCursor)
        sql = """
            SELECT
              bin_to_uuid(jobs.id) AS id,
              jobs.name AS name, jobs.user_id as user_id,
              jobs.status_id as status_id, statuses.name AS status,
              jobs.error_message AS error_message,
              DATE_FORMAT(jobs.creation_date, '%%Y-%%m-%%d %%H:%%i:%%s') AS creation_date,
              DATE_FORMAT(jobs.modified_date, '%%Y-%%m-%%d %%H:%%i:%%s') AS modified_date,
              jobs.is_active
            FROM jobs
            LEFT JOIN statuses ON jobs.status_id = statuses.id
            WHERE jobs.id = uuid_to_bin(%s)
            """
        cur.execute(sql, (job_id,))
        result = cur.fetchone()
        if result is not None:
            map(lambda x: setattr(j, x, result[x]), \
                (val for val in Job.__dbfields + Job.__extfields if val in result))
            sql = """
                SELECT 
                    ju.user_id as user_id, ju.role_id as role_id,
                    role.role_name as role, users.email, 
                    DATE_FORMAT(ju.modified_date, '%%Y-%%m-%%d %%H:%%i:%%s') AS modified_date
                FROM job_users as ju
                    LEFT JOIN job_user_roles role on role.id = ju.role_id
                    LEFT JOIN users on users.id = ju.user_id
                WHERE 
                    ju.job_id = uuid_to_bin(%s)
                """
            cur.execute(sql, (job_id,))
            result = cur.fetchall()
            j.users = result
            return j
        else:
            return None

    @staticmethod
    def list_all_for_user(user_id, config=None):
        db = sql_pool.get_conn()
        results = Job.__list_by_sql_where(db, "jobs.id IN (SELECT job_id from job_users where user_id=%s) AND jobs.is_active=1", (user_id, ))
        return results 

    @staticmethod
    def list_all_for_phenotype(pheno_id, config=None):
        db = sql_pool.get_conn()
        results = Job.__list_by_sql_where(db, "jobs.pheno_id = uuid_to_bin(%s) AND jobs.is_active=1", (pheno_id, ))
        return results 

    @staticmethod
    def list_pending(config=None):
        db = sql_pool.get_conn()
        results = Job.__list_by_sql_where(db, "(statuses.name='queued' OR statuses.name='started')")
        return results

    @staticmethod
    def list_all(config=None):
        db = sql_pool.get_conn()
        results = Job.__list_by_sql_where(db)
        return results

    @staticmethod
    def __list_by_sql_where(db, where="", vals=(), order=""):
        cur = db.cursor(MySQLdb.cursors.DictCursor)
        sql = """
            SELECT bin_to_uuid(jobs.id) AS id, jobs.name AS name, 
              statuses.name AS status, 
              DATE_FORMAT(jobs.creation_date, '%%Y-%%m-%%d %%H:%%i:%%s') AS creation_date, 
              DATE_FORMAT(jobs.modified_date, '%%Y-%%m-%%d %%H:%%i:%%s') AS modified_date,
              users.email as user_email,
              jobs.is_active
            FROM jobs
            LEFT JOIN statuses ON jobs.status_id = statuses.id
            LEFT JOIN users ON jobs.user_id = users.id"""
        if where:
            sql += " WHERE " + where
        if order:
            sql += " ORDER BY " + order
        else:
            sql += " ORDER BY jobs.creation_date DESC"
        cur.execute(sql, vals)
        results = cur.fetchall()
        return results

    @staticmethod
    def update(job_id, new_values):
        updateable_fields = ["name"]
        fields = new_values.keys() 
        values = new_values.values()
        bad_fields = [x for x in fields if x not in updateable_fields]
        try:
            if len(bad_fields)>0:
                raise Exception("Invalid update field: {}".format(", ".join(bad_fields)))
            sql = "UPDATE jobs SET "+ \
                ", ".join(("{}=%s".format(k) for k in fields)) + \
                "WHERE id = uuid_to_bin(%s)"
            db = sql_pool.get_conn()
            cur = db.cursor()
            cur.execute(sql, values + [job_id])
            affected = cur.rowcount
            db.commit()
            result = {"updated": True}
        except Exception as e:
            result = {"updated": False, "error": str(e)}
        return result

    @staticmethod
    def retire(job_id, config=None):
        job = Job.get(job_id, config)
        result = {}
        if job:
            db = sql_pool.get_conn()
            cur = db.cursor()
            sql = "UPDATE jobs SET is_active=0 WHERE id = uuid_to_bin(%s)"
            cur.execute(sql, (job_id, ))
            affected = cur.rowcount
            db.commit()

            result = {"jobs": affected, "found": True, "action": "retire"}
            return result
        else:
            return {"found": False, "action": "retire"}

    @staticmethod
    def purge(job_id, config=None):
        job = Job.get(job_id, config)
        result = {}
        if job:
            db = sql_pool.get_conn()
            cur = db.cursor()
            sql = "DELETE FROM job_users WHERE job_id = uuid_to_bin(%s)"
            cur.execute(sql, (job_id, ))
            users = cur.rowcount
            sql = "DELETE FROM jobs WHERE id = uuid_to_bin(%s)"
            cur.execute(sql, (job_id, ))
            affected = cur.rowcount
            db.commit()

            removed = False
            job_directory = job.root_path 
            if os.path.isdir(job_directory) and affected>0:
                try:
                    shutil.rmtree(job_directory)
                    removed = True
                except:
                    pass

            result = {"jobs": affected, "users": users, "files": removed, "found": True, "action": "purge"}
            return result
        else:
            return {"found": False, "action": "purge"}

    @staticmethod
    def share_add_email(job_id, email, current_user, role=0, config=None):
        ex = None
        db = sql_pool.get_conn()
        user = User.from_email(email, db)
        if user is None:
            user = User.create({"email": email, "can_analyze": False}, db)["user"]
        try:
            cur = db.cursor()
            sql = """
                INSERT INTO job_users (job_id, user_id, role_id, created_by)
                VALUES (uuid_to_bin(%s), %s, %s, %s)
                """
            cur.execute(sql, (job_id, user.rid, role, current_user.rid))
            db.commit()
        except:
            ex = sys.exc_info()[0]
        finally:
            cur.close()
        if ex is not None:
            raise ex
        return True

    @staticmethod
    def share_drop_email(job_id, email, current_user, role=0, config=None):
        ex = None
        db = sql_pool.get_conn()
        user = User.from_email(email, db)
        if user is None:
            return False
        try:
            cur = db.cursor()
            sql = """
                DELETE FROM job_users
                WHERE job_id=uuid_to_bin(%s) AND user_id=%s
                """
            cur.execute(sql, (job_id, user.rid))
            db.commit()
            success = True
        except:
            ex = sys.exc_info()[0]
        finally:
            cur.close()
        if ex is not None:
            raise ex
        return True

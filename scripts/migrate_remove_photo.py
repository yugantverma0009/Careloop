"""
scripts/migrate_remove_photo.py

Database migration script: Completely and cleanly removes all photo objects, tables,
dependent records, and ENUM values from the CareLoop MySQL database.

Order of Execution:
1. Report counts of dependent rows.
2. Delete dependent rows (scheduled_actions with Photo_Request, agent_autonomy with photo_request,
   agent_proposals with Suggest_Photo, flags with source_type Photo).
3. Drop table wound_photos.
4. Remove 'Photo' / 'Photo_Request' / 'Suggest_Photo' from ENUM columns with ALTER TABLE.
5. Print audit summary of completed migration.
"""

import os
import pymysql
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), "..", "backend", ".env")
load_dotenv(env_path)

db_host = os.getenv("DB_HOST", "localhost")
db_port = int(os.getenv("DB_PORT", "3306"))
db_user = os.getenv("DB_USER", "careloop_api")
db_password = os.getenv("DB_PASSWORD", "careloop_dev_pass")
db_name = os.getenv("DB_NAME", "careloop")


def run_migration():
    print(f"Connecting to MySQL database '{db_name}' on {db_host}:{db_port}...")
    conn = pymysql.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        database=db_name,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False
    )
    cur = conn.cursor()

    try:
        print("\n--- STEP 1: Reporting Dependent Row Counts ---")
        cur.execute("SELECT COUNT(*) AS c FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='wound_photos'")
        has_table = cur.fetchone()["c"] > 0
        photo_count = 0
        if has_table:
            cur.execute("SELECT COUNT(*) AS c FROM wound_photos")
            photo_count = cur.fetchone()["c"]
        print(f"  • wound_photos rows: {photo_count}")

        cur.execute("SELECT COUNT(*) AS c FROM scheduled_actions WHERE action_type='Photo_Request'")
        sched_count = cur.fetchone()["c"]
        print(f"  • scheduled_actions (Photo_Request): {sched_count}")

        cur.execute("SELECT COUNT(*) AS c FROM agent_proposals WHERE proposal_type='Suggest_Photo'")
        prop_count = cur.fetchone()["c"]
        print(f"  • agent_proposals (Suggest_Photo): {prop_count}")

        cur.execute("SELECT COUNT(*) AS c FROM flags WHERE source_type='Photo'")
        flag_count = cur.fetchone()["c"]
        print(f"  • flags (source_type Photo): {flag_count}")

        cur.execute("SELECT COUNT(*) AS c FROM agent_autonomy WHERE action_type='photo_request'")
        auto_count = cur.fetchone()["c"]
        print(f"  • agent_autonomy (photo_request): {auto_count}")

        print("\n--- STEP 2: Deleting Dependent Rows ---")
        cur.execute("DELETE FROM scheduled_actions WHERE action_type='Photo_Request'")
        print(f"  ✓ Deleted {cur.rowcount} scheduled_actions row(s)")

        cur.execute("DELETE FROM agent_proposals WHERE proposal_type='Suggest_Photo'")
        print(f"  ✓ Deleted {cur.rowcount} agent_proposals row(s)")

        cur.execute("DELETE FROM flags WHERE source_type='Photo'")
        print(f"  ✓ Deleted {cur.rowcount} flags row(s)")

        cur.execute("DELETE FROM agent_autonomy WHERE action_type='photo_request'")
        print(f"  ✓ Deleted {cur.rowcount} agent_autonomy row(s)")

        conn.commit()

        print("\n--- STEP 3: Dropping Table wound_photos ---")
        if has_table:
            # Check foreign keys pointing to wound_photos
            cur.execute("""
                SELECT CONSTRAINT_NAME, TABLE_NAME
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE REFERENCED_TABLE_NAME = 'wound_photos' AND TABLE_SCHEMA = DATABASE()
            """)
            fks = cur.fetchall()
            for fk in fks:
                print(f"  • Dropping foreign key {fk['CONSTRAINT_NAME']} from {fk['TABLE_NAME']}...")
                cur.execute(f"ALTER TABLE `{fk['TABLE_NAME']}` DROP FOREIGN KEY `{fk['CONSTRAINT_NAME']}`")

            cur.execute("DROP TABLE IF EXISTS `wound_photos`")
            print("  ✓ Table `wound_photos` successfully dropped.")

        print("\n--- STEP 4: Altering ENUM Columns ---")
        print("  • Altering flags.source_type (removing 'Photo')...")
        cur.execute("""
            ALTER TABLE flags
            MODIFY source_type enum('Sensor','Symptom','Medication','Device','Emergency','Fall','Checkin','SOS') NOT NULL
        """)
        print("  ✓ flags.source_type updated.")

        print("  • Altering scheduled_actions.action_type (removing 'Photo_Request')...")
        cur.execute("""
            ALTER TABLE scheduled_actions
            MODIFY action_type enum('Dose_Reminder','Checkin_Prompt','Fall_Prompt','Plan_Prompt','Welcome_Call_Task','SOS_Repeat') NOT NULL
        """)
        print("  ✓ scheduled_actions.action_type updated.")

        print("  • Altering agent_proposals.proposal_type (removing 'Suggest_Photo')...")
        cur.execute("""
            ALTER TABLE agent_proposals
            MODIFY proposal_type enum('Suggest_Call','Suggest_Plan_Review') NOT NULL
        """)
        print("  ✓ agent_proposals.proposal_type updated.")

        conn.commit()

        print("\n--- STEP 5: Verification ---")
        cur.execute("SHOW TABLES LIKE 'wound_photos'")
        remaining_tables = cur.fetchall()
        print(f"  • wound_photos table exists: {len(remaining_tables) > 0}")
        assert len(remaining_tables) == 0, "Error: wound_photos table still exists!"

        cur.execute("SELECT COLUMN_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='flags' AND COLUMN_NAME='source_type'")
        fl_enum = cur.fetchone()["COLUMN_TYPE"]
        print(f"  • flags.source_type: {fl_enum}")
        assert "Photo" not in fl_enum, "Error: 'Photo' still in flags.source_type ENUM!"

        cur.execute("SELECT COLUMN_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='scheduled_actions' AND COLUMN_NAME='action_type'")
        sa_enum = cur.fetchone()["COLUMN_TYPE"]
        print(f"  • scheduled_actions.action_type: {sa_enum}")
        assert "Photo_Request" not in sa_enum, "Error: 'Photo_Request' still in scheduled_actions.action_type ENUM!"

        cur.execute("SELECT COLUMN_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='agent_proposals' AND COLUMN_NAME='proposal_type'")
        ap_enum = cur.fetchone()["COLUMN_TYPE"]
        print(f"  • agent_proposals.proposal_type: {ap_enum}")
        assert "Suggest_Photo" not in ap_enum, "Error: 'Suggest_Photo' still in agent_proposals.proposal_type ENUM!"

        print("\n✅ Layer D Database Migration completed cleanly and successfully!")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed with error: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()

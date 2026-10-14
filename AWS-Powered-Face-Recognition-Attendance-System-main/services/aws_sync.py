"""Optional, best-effort sync to S3 / DynamoDB. Never raises; offline SQLite stays the source of truth."""
import os


def _enabled():
    return os.getenv("SIMULATION_MODE", "True").lower() == "false" and bool(os.getenv("S3_BUCKET_NAME"))


def _boto(kind):
    import boto3
    return boto3.client(kind) if kind == "s3" else boto3.resource(kind)


def sync_student(name, roll, photo_path, photo_name):
    if not _enabled():
        return
    try:
        _boto("s3").upload_file(photo_path, os.environ["S3_BUCKET_NAME"], f"students/{photo_name}")
        _boto("dynamodb").Table(os.getenv("DYNAMODB_TABLE_STUDENTS", "Students")).put_item(
            Item={"roll_number": roll, "name": name, "photo": photo_name})
    except Exception as exc:
        print("AWS sync (student) skipped:", exc)


def sync_attendance(roll, name, date, time):
    if not _enabled():
        return
    try:
        _boto("dynamodb").Table(os.getenv("DYNAMODB_TABLE_ATTENDANCE", "Attendance")).put_item(
            Item={"roll_number": roll, "date": date, "name": name, "time": time, "status": "Present"})
    except Exception as exc:
        print("AWS sync (attendance) skipped:", exc)

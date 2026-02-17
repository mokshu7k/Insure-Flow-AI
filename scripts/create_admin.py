"""
Create Admin User Script
Run this to create the initial admin user
"""
import sys
import os
from getpass import getpass

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import hash_password
import uuid


def create_admin_user():
    """Create admin user interactively"""
    
    print("=" * 50)
    print("InsureFlow-AI - Create Admin User")
    print("=" * 50)
    
    email = input("Admin Email: ").strip()
    if not email:
        print("Error: Email is required")
        return
    
    password = getpass("Admin Password: ")
    password_confirm = getpass("Confirm Password: ")
    
    if password != password_confirm:
        print("Error: Passwords don't match")
        return
    
    if len(password) < 8:
        print("Error: Password must be at least 8 characters")
        return
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            print(f"Error: User with email {email} already exists")
            return
        
        # Create admin user
        admin_user = User(
            id=uuid.uuid4(),
            email=email,
            password_hash=hash_password(password),
            role="INSURER_ADMIN",
            is_active=True
        )
        
        db.add(admin_user)
        db.commit()
        
        print("\n✓ Admin user created successfully!")
        print(f"  Email: {email}")
        print(f"  Role: INSURER_ADMIN")
        print(f"  User ID: {admin_user.id}")
        
    except Exception as e:
        db.rollback()
        print(f"Error creating admin user: {e}")
    
    finally:
        db.close()


if __name__ == "__main__":
    create_admin_user()
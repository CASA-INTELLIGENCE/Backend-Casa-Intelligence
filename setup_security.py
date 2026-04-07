"""
Setup script for Casa Intelligence
Generates encryption key and helps configure .env file
"""
import os
import sys
from pathlib import Path
from cryptography.fernet import Fernet


def main():
    print("="*60)
    print(" Casa Intelligence - Security Setup")
    print("="*60)
    print()
    
    env_path = Path(__file__).parent / ".env"
    env_example_path = Path(__file__).parent / ".env.example"
    
    # Check if .env exists
    if not env_path.exists():
        if env_example_path.exists():
            print("Creating .env from .env.example...")
            env_path.write_text(env_example_path.read_text())
            print(f"✅ Created {env_path}")
        else:
            print(f"❌ ERROR: {env_example_path} not found!")
            sys.exit(1)
    
    # Read current .env
    env_content = env_path.read_text()
    
    # Check if ENCRYPTION_KEY is already set
    if "ENCRYPTION_KEY=" in env_content and not env_content.count("ENCRYPTION_KEY=your_"):
        # Check if key looks valid
        for line in env_content.split("\n"):
            if line.startswith("ENCRYPTION_KEY="):
                key = line.split("=", 1)[1].strip()
                if len(key) == 44:
                    print("✅ ENCRYPTION_KEY already configured")
                    print()
                    print("Next steps:")
                    print("1. Update other credentials in .env file:")
                    print("   - GEMINI_API_KEY (get from https://aistudio.google.com/app/apikey)")
                    print("   - ROUTER_PASSWORD")
                    print("   - AMAZON_EMAIL and AMAZON_PASSWORD (optional)")
                    print()
                    print("2. Start the backend:")
                    print("   python main.py")
                    print()
                    return
    
    # Generate new encryption key
    print("Generating new ENCRYPTION_KEY...")
    new_key = Fernet.generate_key().decode()
    print(f"✅ Generated key: {new_key}")
    print()
    
    # Update .env
    updated = False
    new_lines = []
    
    for line in env_content.split("\n"):
        if line.startswith("ENCRYPTION_KEY="):
            new_lines.append(f"ENCRYPTION_KEY={new_key}")
            updated = True
            print("✅ Updated ENCRYPTION_KEY in .env")
        else:
            new_lines.append(line)
    
    if not updated:
        # Add at the end
        new_lines.append("")
        new_lines.append("# Auto-generated encryption key")
        new_lines.append(f"ENCRYPTION_KEY={new_key}")
        print("✅ Added ENCRYPTION_KEY to .env")
    
    # Write back
    env_path.write_text("\n".join(new_lines))
    
    print()
    print("="*60)
    print(" ⚠️  IMPORTANT SECURITY NOTES")
    print("="*60)
    print()
    print("1. NEVER commit .env to git!")
    print("   - Already added to .gitignore ✓")
    print()
    print("2. ROTATE your credentials if they were exposed:")
    print("   - Gemini API Key: https://aistudio.google.com/app/apikey")
    print("   - Router password: Access router admin panel")
    print("   - Amazon password: https://www.amazon.com/ap/forgotpassword")
    print()
    print("3. Update the following in .env:")
    print(f"   - Edit: {env_path}")
    print("   - Set GEMINI_API_KEY")
    print("   - Set ROUTER_PASSWORD")
    print("   - (Optional) Set AMAZON_EMAIL and AMAZON_PASSWORD")
    print()
    print("="*60)
    print()
    print("Setup complete! Run: python main.py")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

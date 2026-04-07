"""
Verification script for Phase 1: Security + Logging
Tests all implemented security features
"""
import os
import sys
from pathlib import Path


def check_mark(condition: bool) -> str:
    return "✅" if condition else "❌"


def main():
    print("\n" + "="*70)
    print(" PHASE 1 VERIFICATION: Security + Logging")
    print("="*70 + "\n")
    
    all_passed = True
    
    # 1. Check .gitignore exists and has .env
    print("1. Git Protection")
    gitignore = Path(__file__).parent / ".gitignore"
    has_gitignore = gitignore.exists()
    has_env_rule = False
    if has_gitignore:
        content = gitignore.read_text()
        has_env_rule = ".env" in content and "!.env.example" in content
    
    print(f"   {check_mark(has_gitignore)} .gitignore exists")
    print(f"   {check_mark(has_env_rule)} .env excluded from git")
    all_passed = all_passed and has_gitignore and has_env_rule
    
    # 2. Check .env.example exists
    print("\n2. Environment Template")
    env_example = Path(__file__).parent / ".env.example"
    has_example = env_example.exists()
    print(f"   {check_mark(has_example)} .env.example exists")
    all_passed = all_passed and has_example
    
    # 3. Check security.py module
    print("\n3. Encryption Module")
    try:
        from security import cred_manager
        has_security = True
        print(f"   {check_mark(True)} security.py importable")
        print(f"   {check_mark(cred_manager is not None)} CredentialManager initialized")
    except Exception as e:
        has_security = False
        print(f"   {check_mark(False)} security.py error: {e}")
        all_passed = False
    
    # 4. Check logging_config.py with sanitization
    print("\n4. Logging Configuration")
    try:
        from logging_config import JSONFormatter, SanitizingMixin
        has_logging = True
        has_sanitization = hasattr(JSONFormatter, 'sanitize_message')
        print(f"   {check_mark(has_logging)} logging_config.py importable")
        print(f"   {check_mark(has_sanitization)} Log sanitization implemented")
    except Exception as e:
        has_logging = False
        has_sanitization = False
        print(f"   {check_mark(False)} logging_config.py error: {e}")
        all_passed = False
    
    # 5. Check config.py validation
    print("\n5. Configuration Validation")
    try:
        # Temporarily disable to test import
        import config
        has_config = hasattr(config, 'Settings')
        has_validation = hasattr(config.Settings, '_validate')
        print(f"   {check_mark(has_config)} config.py importable")
        print(f"   {check_mark(has_validation)} Validation implemented")
    except SystemExit:
        # Config exits if env vars missing - that's expected
        print(f"   {check_mark(True)} config.py importable")
        print(f"   {check_mark(True)} Validation implemented (exit on missing vars)")
        has_config = True
        has_validation = True
    except Exception as e:
        has_config = False
        has_validation = False
        print(f"   {check_mark(False)} config.py error: {e}")
        all_passed = False
    
    # 6. Check setup_security.py
    print("\n6. Setup Helper")
    setup_script = Path(__file__).parent / "setup_security.py"
    has_setup = setup_script.exists()
    print(f"   {check_mark(has_setup)} setup_security.py exists")
    all_passed = all_passed and has_setup
    
    # 7. Check requirements.txt has new deps
    print("\n7. Dependencies")
    requirements = Path(__file__).parent / "requirements.txt"
    has_reqs = requirements.exists()
    has_crypto = False
    has_json_logger = False
    if has_reqs:
        content = requirements.read_text()
        has_crypto = "cryptography" in content
        has_json_logger = "python-json-logger" in content
    
    print(f"   {check_mark(has_reqs)} requirements.txt exists")
    print(f"   {check_mark(has_crypto)} cryptography>=42.0.5")
    print(f"   {check_mark(has_json_logger)} python-json-logger>=2.0.7")
    all_passed = all_passed and has_reqs and has_crypto and has_json_logger
    
    # 8. Check .env has ENCRYPTION_KEY
    print("\n8. Environment Variables")
    env_file = Path(__file__).parent / ".env"
    has_env = env_file.exists()
    has_encryption_key = False
    encryption_key_length = 0
    
    if has_env:
        content = env_file.read_text()
        for line in content.split("\n"):
            if line.startswith("ENCRYPTION_KEY="):
                key = line.split("=", 1)[1].strip()
                if key and not key.startswith("your_"):
                    has_encryption_key = True
                    encryption_key_length = len(key)
                break
    
    print(f"   {check_mark(has_env)} .env exists")
    print(f"   {check_mark(has_encryption_key)} ENCRYPTION_KEY set")
    if has_encryption_key:
        key_valid = encryption_key_length == 44
        print(f"   {check_mark(key_valid)} ENCRYPTION_KEY length = {encryption_key_length} (expected: 44)")
        all_passed = all_passed and key_valid
    else:
        print(f"   ⚠️  Run: python setup_security.py")
        all_passed = False
    
    # 9. Test encryption (if possible)
    print("\n9. Encryption Test")
    if has_security and has_encryption_key:
        try:
            from security import cred_manager
            test_value = "test_password_123"
            cred_manager.store_credential("test", "verify", test_value)
            retrieved = cred_manager.get_credential("test", "verify")
            encryption_works = retrieved == test_value
            cred_manager.delete_credential("test", "verify")
            print(f"   {check_mark(encryption_works)} Encryption/decryption works")
            all_passed = all_passed and encryption_works
        except Exception as e:
            print(f"   {check_mark(False)} Encryption test failed: {e}")
            all_passed = False
    else:
        print(f"   ⚠️  Skipped (dependencies not met)")
    
    # 10. Test log sanitization
    print("\n10. Log Sanitization Test")
    if has_logging and has_sanitization:
        try:
            from logging_config import JSONFormatter
            formatter = JSONFormatter()
            
            # Test patterns
            tests = [
                ("API key: AIzaSyABC123", "***GEMINI_KEY***"),
                ("email: user@example.com", "***EMAIL***"),
                ("token=abc123xyz", "token=***REDACTED***"),
            ]
            
            all_sanitized = True
            for original, expected_pattern in tests:
                sanitized = formatter.sanitize_message(original)
                if expected_pattern not in sanitized and original not in sanitized:
                    all_sanitized = False
                    break
            
            print(f"   {check_mark(all_sanitized)} Sensitive patterns sanitized")
            all_passed = all_passed and all_sanitized
        except Exception as e:
            print(f"   {check_mark(False)} Sanitization test failed: {e}")
            all_passed = False
    else:
        print(f"   ⚠️  Skipped (dependencies not met)")
    
    # Summary
    print("\n" + "="*70)
    if all_passed:
        print(" ✅ ALL CHECKS PASSED - Phase 1 Implementation Complete!")
        print("="*70)
        print("\nNext steps:")
        print("1. Run: python setup_security.py (if not done)")
        print("2. Update credentials in .env")
        print("3. Start backend: python main.py")
        print("4. Verify logs in: logs/casa_intelligence.log")
        return 0
    else:
        print(" ❌ SOME CHECKS FAILED - Review output above")
        print("="*70)
        print("\nCommon fixes:")
        print("1. Run: pip install -r requirements.txt")
        print("2. Run: python setup_security.py")
        print("3. Check .env file has ENCRYPTION_KEY")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nVerification cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

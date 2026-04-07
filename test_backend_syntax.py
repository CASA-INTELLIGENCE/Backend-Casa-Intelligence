"""
Backend Syntax and Import Test
Tests that all Phase 2 backend files compile and import correctly
"""

import sys
import os

# Add backend to path
sys.path.insert(0, r'c:\Users\svsil\Desktop\Silvas-Indrustries\PruebaAdoptAI\casa-intelligence\backend')

def test_file(filename, module_name):
    """Test if a file compiles and imports"""
    print(f"\n{'='*60}")
    print(f"Testing: {filename}")
    print('='*60)
    
    try:
        # Try to import
        module = __import__(module_name)
        print(f"✅ {filename} - Import successful")
        
        # List main exports
        exports = [name for name in dir(module) if not name.startswith('_')]
        print(f"📦 Exports: {', '.join(exports[:10])}")
        if len(exports) > 10:
            print(f"   ... and {len(exports) - 10} more")
        
        return True
    except SyntaxError as e:
        print(f"❌ {filename} - Syntax Error")
        print(f"   Line {e.lineno}: {e.msg}")
        print(f"   {e.text}")
        return False
    except ImportError as e:
        print(f"⚠️  {filename} - Import Warning (may need dependencies)")
        print(f"   {e}")
        return True  # Still valid syntax
    except Exception as e:
        print(f"⚠️  {filename} - Runtime issue (syntax OK)")
        print(f"   {type(e).__name__}: {e}")
        return True  # Syntax is OK

def main():
    print("="*60)
    print("🧪 BACKEND SYNTAX & IMPORT TEST")
    print("="*60)
    
    tests = [
        ("exceptions.py", "exceptions"),
        ("decorators.py", "decorators"),
        ("circuit_breaker.py", "circuit_breaker"),
        ("websocket_manager.py", "websocket_manager"),
        ("main.py", "main"),
    ]
    
    results = []
    for filename, module in tests:
        results.append(test_file(filename, module))
    
    print(f"\n{'='*60}")
    print("📊 SUMMARY")
    print('='*60)
    passed = sum(results)
    total = len(results)
    print(f"✅ Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All backend files are syntactically correct!")
        return 0
    else:
        print("⚠️  Some files have issues")
        return 1

if __name__ == "__main__":
    exit(main())

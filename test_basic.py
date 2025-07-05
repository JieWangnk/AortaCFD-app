#!/usr/bin/env python3
"""
Basic test to verify the testing infrastructure works.
"""

def test_imports():
    """Test that we can import the main modules."""
    try:
        # Test basic config imports
        from config.builder import ConfigBuilder, deep_merge
        print("✓ Config imports successful")
        
        # Test basic utility imports
        from aortacfd_lib.utils.logger import Logger
        print("✓ Logger import successful")
        
        from aortacfd_lib.utils.runner import Runner
        print("✓ Runner import successful")
        
        from aortacfd_lib.utils.format_points import format_points
        print("✓ Format points import successful")
        
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def test_workflow_import():
    """Test workflow import separately to isolate issues."""
    try:
        # This might fail due to missing dependencies in tasks
        from workflow.manager import WorkflowManager
        print("✓ Workflow imports successful")
        return True
    except ImportError as e:
        print(f"✗ Workflow import failed: {e}")
        print("  This is expected if STL/numpy dependencies are missing")
        return False

def test_deep_merge():
    """Test the deep_merge function."""
    try:
        from config.builder import deep_merge
        
        dest = {"a": 1, "b": 2}
        source = {"b": 3, "c": 4}
        result = deep_merge(dest, source)
        
        expected = {"a": 1, "b": 3, "c": 4}
        assert result == expected, f"Expected {expected}, got {result}"
        print("✓ Deep merge test passed")
        return True
    except Exception as e:
        print(f"✗ Deep merge test failed: {e}")
        return False

def test_format_points():
    """Test the format_points function."""
    try:
        from aortacfd_lib.utils.format_points import format_points
        
        points = [(0.0, 0.0, 0.0), (1.0, 1.0, 1.0)]
        result = format_points(points)
        
        # The function now uses different formatting, so adjust expectations
        assert "0.0 0.0 0.0" in result
        assert "1.0 1.0 1.0" in result
        print("✓ Format points test passed")
        return True
    except Exception as e:
        print(f"✗ Format points test failed: {e}")
        return False

def test_runner():
    """Test the Runner class."""
    try:
        from aortacfd_lib.utils.runner import Runner
        
        runner = Runner()
        # Test that runner can be instantiated
        assert runner is not None
        print("✓ Runner test passed")
        return True
    except Exception as e:
        print(f"✗ Runner test failed: {e}")
        return False

if __name__ == "__main__":
    print("Running basic tests...")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_workflow_import,
        test_deep_merge,
        test_format_points,
        test_runner
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        if test():
            passed += 1
        else:
            failed += 1
    
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! Testing infrastructure is working.")
    else:
        print("❌ Some tests failed. Check the errors above.")
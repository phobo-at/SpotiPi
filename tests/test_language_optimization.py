#!/usr/bin/env python3
"""
Test script to validate language optimization changes
"""

from src.utils.translations import t_api, get_user_language, TRANSLATIONS

class MockRequest:
    def __init__(self, accept_language="en"):
        self.headers = {"Accept-Language": accept_language}

def test_translations():
    """Test that all API messages work properly"""
    print("🧪 Testing Language Optimization...")
    
    # Test German
    req_de = MockRequest("de-DE,de;q=0.9")
    lang_de = get_user_language(req_de)
    
    # Test English  
    req_en = MockRequest("en-US,en;q=0.9")
    lang_en = get_user_language(req_en)
    
    # Test some key translations
    test_keys = [
        "auth_required",
        "invalid_time_format", 
        "alarm_settings_saved",
        "volume_saved",
        "playback_started",
        "page_not_found"
    ]
    
    print(f"Detected languages: DE={lang_de}, EN={lang_en}")
    print("\n📝 Translation Tests:")
    
    all_passed = True
    
    for key in test_keys:
        try:
            de_text = t_api(key, req_de)
            en_text = t_api(key, req_en)
            
            # Check that German and English are different (for most keys)
            if de_text != en_text:
                print(f"✅ {key:20} DE: {de_text[:30]}... | EN: {en_text[:30]}...")
            else:
                print(f"⚠️  {key:20} Same text in both languages: {de_text}")
                
        except Exception as e:
            print(f"❌ {key:20} ERROR: {e}")
            all_passed = False
    
    # Test parameterized translations
    print("\n🔧 Parameter Tests:")
    try:
        volume_test = t_api("volume_set_saved", req_de, volume=75)
        print(f"✅ Parameterized: {volume_test}")
    except Exception as e:
        print(f"❌ Parameterized: {e}")
        all_passed = False
    
    # Check coverage
    de_keys = set(TRANSLATIONS['de'].keys())
    en_keys = set(TRANSLATIONS['en'].keys())
    
    missing_de = en_keys - de_keys
    missing_en = de_keys - en_keys
    
    print(f"\n📊 Coverage:")
    print(f"✅ German translations: {len(de_keys)}")
    print(f"✅ English translations: {len(en_keys)}")
    
    if missing_de:
        print(f"❌ Missing German keys: {missing_de}")
        all_passed = False
    if missing_en:
        print(f"❌ Missing English keys: {missing_en}")
        all_passed = False
        
    if all_passed:
        print(f"\n🎉 All tests passed! Language optimization is working correctly.")
    else:
        print(f"\n⚠️  Some tests failed. Please review the issues above.")
    
    # Return None for pytest compatibility
    assert all_passed, "Some translation tests failed"

if __name__ == "__main__":
    test_translations()
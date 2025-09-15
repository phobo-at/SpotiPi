# CSS Modularization Plan

## Current State
- **Single File**: `static/css/style.css` (1536 lines)
- **Well Organized**: Clear section markers with emoji headers
- **Good Structure**: CSS custom properties, logical grouping
- **Challenge**: Large file becoming difficult to maintain

## Proposed Module Structure

### 1. Core Foundation
```
static/css/
├── main.css              # Import orchestrator
├── foundation/
│   ├── variables.css     # 🎨 Color Scheme & Core Variables
│   ├── base.css          # 📄 Base Layout + body/html
│   └── utilities.css     # 🔧 Utility Classes
```

### 2. Component Modules
```
├── components/
│   ├── forms.css         # 📝 Form Elements
│   ├── buttons.css       # 🔘 Buttons
│   ├── toggles.css       # 🔘 Toggle Switches
│   ├── sliders.css       # 🎚️ Slider + 🔊️ Volume Controls
│   ├── notifications.css # 🔔 Notifications
│   └── tabs.css          # 🔗 Shared Tab Components
```

### 3. Feature-Specific Modules
```
├── features/
│   ├── alarm.css         # ⏰ Alarm-specific Styles
│   ├── sleep.css         # 😴 Sleep-specific Styles
│   ├── music.css         # 🎵 Current Track + Music Library
│   ├── playlists.css     # 🎵 Playlist Modal + Content
│   └── devices.css       # 🔊 Device Selection Modal
```

### 4. Layout & PWA
```
├── layout/
│   ├── responsive.css    # 📱 Responsive Adjustments
│   ├── pwa.css           # 📱 PWA iOS Status-Bar
│   └── main-layout.css   # 🏗️ Main Layout Components
```

## Implementation Strategy

### Phase 1: Setup Module Structure
1. Create directory structure
2. Create `main.css` as import orchestrator
3. Update HTML templates to use `main.css`

### Phase 2: Extract Foundation
1. Move CSS variables to `foundation/variables.css`
2. Extract base styles to `foundation/base.css`
3. Move utility classes to `foundation/utilities.css`

### Phase 3: Modularize Components
1. Extract reusable UI components
2. Maintain existing class names (no breaking changes)
3. Test each module extraction

### Phase 4: Feature-Specific Extraction
1. Move page-specific styles to feature modules
2. Consolidate related styles (e.g., all music-related styles)

### Phase 5: Layout & PWA
1. Extract responsive styles
2. Move PWA-specific styles
3. Organize layout components

## Import Order Strategy

```css
/* main.css */
/* 1. Foundation */
@import url('foundation/variables.css');
@import url('foundation/base.css');
@import url('foundation/utilities.css');

/* 2. Components (order by dependency) */
@import url('components/forms.css');
@import url('components/buttons.css');
@import url('components/toggles.css');
@import url('components/sliders.css');
@import url('components/notifications.css');
@import url('components/tabs.css');

/* 3. Layout */
@import url('layout/main-layout.css');
@import url('layout/responsive.css');
@import url('layout/pwa.css');

/* 4. Features (alphabetical) */
@import url('features/alarm.css');
@import url('features/devices.css');
@import url('features/music.css');
@import url('features/playlists.css');
@import url('features/sleep.css');
```

## Migration Benefits

### Development
- **Maintainability**: Smaller, focused files
- **Team Collaboration**: Reduced merge conflicts
- **Feature Development**: Easier to work on specific features
- **Code Organization**: Logical separation of concerns

### Performance
- **Selective Loading**: Future ability to load only needed CSS
- **Browser Caching**: Individual module caching
- **Build Optimization**: Future minification per module

### Architecture
- **Scalability**: Easy to add new feature styles
- **Dependency Management**: Clear import relationships
- **Testing**: Easier to test individual components

## Backward Compatibility
- **No Class Changes**: All existing classes remain unchanged
- **Same CSS Output**: Final compiled CSS should be identical
- **Template Compatibility**: Only change CSS import in templates
- **Deployment**: No Pi-specific changes needed

## Implementation Timeline

### Immediate (1 session)
- [ ] Create directory structure
- [ ] Set up `main.css` orchestrator
- [ ] Extract CSS variables to `foundation/variables.css`
- [ ] Update templates to use modular CSS

### Short-term (next sessions)
- [ ] Extract base styles and utilities
- [ ] Modularize form components
- [ ] Extract button and toggle styles

### Medium-term
- [ ] Feature-specific module extraction
- [ ] Responsive and PWA module organization
- [ ] Performance testing and optimization

## Notes
- Current CSS is well-organized, making extraction straightforward
- Emoji section headers will become module names
- No breaking changes to existing functionality
- Follows same modular pattern as JavaScript modules
- Maintains Pi Zero compatibility and performance
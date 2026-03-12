# Debugging Settings View Issue in SimCraft Web

## Problem
The settings view (`frontend/views/ustawienia.html`) was showing "Alpine Expression Error: form is not defined" (later "form_main_character_name is not defined") when trying to bind form inputs like:
```html
<select x-model="form_main_character_name" @change="onCharSelect()" ...>
```

## Root Cause Analysis
1. **Timing Issues**: The settings view was loaded dynamically via AJAX in `app.js.loadView()`, and there were race conditions between:
   - When `window.settingsMixin` became available
   - When Alpine.js initialized the view
   - When `window.__alpineApp` was set (needed for settingsMixin.init())

2. **Data Scope Issues**: The settings view was trying to use its own `x-data` but wasn't properly inheriting or accessing the mixin data.

3. **Initialization Order**: `settingsMixin.init()` was running before `window.__alpineApp` was properly set by the main app initialization.

## Solution Implemented
1. **Removed x-data from settings view**: Changed the settings view container from:
   ```html
   <div class="settings-view" x-data="window.settingsMixin()" x-init="init()">
   ```
   to:
   ```html
   <div class="settings-view" x-init="init()">
   ```
   This allows the view to inherit data from the parent `app()` component.

2. **Ensured proper mixin integration**: In `frontend/app.js`:
   - `settingsMixin()` is called and its return value is merged into the app state via `mergeMixins(state, window.settingsMixin())`
   - This makes properties like `form_main_character_name` available directly in the app state

3. **Fixed initialization timing**: In `frontend/settings.js`, the `init()` method now waits for `window.__alpineApp` to be defined before proceeding:
   ```javascript
   async init() {
     console.log('[Settings] init called');
     // Wait for window.__alpineApp to be defined
     if (!window.__alpineApp) {
       console.log('[Settings] window.__alpineApp not defined, waiting...');
       await new Promise(resolve => {
         const check = () => {
           if (window.__alpineApp) resolve();
           else setTimeout(check, 50);
         };
         check();
       });
     }
     // ... rest of init
   }
   ```

## Key Files Modified
- `frontend/views/ustawienia.html`: Removed x-data attribute
- `frontend/app.js`: Added `window.app = app` and ensured proper mixin merging
- `frontend/settings.js`: Added wait for `window.__alpineApp` in init()

## Why This Works
- The settings view now inherits its data scope from the parent `app()` component
- The `settingsMixin()` function's return value is properly merged into `app.state`
- The `init()` method waits for the main app to fully initialize before accessing `window.__alpineApp`
- All form properties (`form_main_character_name`, etc.) are available in the inherited scope

## Testing
After applying these changes, the settings view should load without "form is not defined" errors, and form bindings should work correctly.

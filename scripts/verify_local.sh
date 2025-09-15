#!/bin/bash

# 🔍 Quick Local Migration Verification
# Verifies local environment after migration to spotipi

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 Quick Local Migration Check${NC}"
echo "================================"

# Check if we're in spotipi directory
if [[ $(basename "$PWD") == "spotipi" ]]; then
    echo -e "${GREEN}✅ In correct directory: spotipi${NC}"
else
    echo -e "${RED}❌ Not in spotipi directory (currently in: $(basename "$PWD"))${NC}"
    exit 1
fi

# Check for key files
KEY_FILES=(
    "run.py"
    "src/app.py"
    "src/config.py"
    "scripts/deploy_to_pi.sh"
    "MIGRATION_GUIDE.md"
)

echo -e "\n${BLUE}Checking essential files...${NC}"
for file in "${KEY_FILES[@]}"; do
    if [[ -f "$file" ]]; then
        echo -e "${GREEN}✅ $file${NC}"
    else
        echo -e "${RED}❌ $file${NC}"
    fi
done

# Check for old backup scripts
echo -e "\n${BLUE}Checking backup files...${NC}"
BACKUP_FILES=(
    "scripts/deploy_to_pi_old.sh"
    "scripts/toggle_logging_old.sh"
)

for file in "${BACKUP_FILES[@]}"; do
    if [[ -f "$file" ]]; then
        echo -e "${GREEN}✅ Backup exists: $file${NC}"
    else
        echo -e "${YELLOW}⚠️  No backup found: $file${NC}"
    fi
done

# Check if scripts are executable
echo -e "\n${BLUE}Checking script permissions...${NC}"
EXECUTABLE_SCRIPTS=(
    "scripts/deploy_to_pi.sh"
    "scripts/run_tests.sh"
    "scripts/verify_migration.sh"
)

for script in "${EXECUTABLE_SCRIPTS[@]}"; do
    if [[ -x "$script" ]]; then
        echo -e "${GREEN}✅ Executable: $script${NC}"
    else
        echo -e "${YELLOW}⚠️  Not executable: $script${NC}"
    fi
done

echo -e "\n${GREEN}🎉 Local verification complete!${NC}"
echo -e "${BLUE}To verify Pi migration, run: ./scripts/verify_migration.sh${NC}"
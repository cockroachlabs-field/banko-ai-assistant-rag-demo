#!/bin/bash

# Script to systematically merge Dependabot PRs
# Priority: Security updates first, then framework updates

echo "🔐 Merging Dependabot Security Updates..."

# Security-critical updates (merge these first)
SECURITY_UPDATES=(
    "certifi-2024.7.4"
    "requests-2.32.4" 
    "urllib3-2.5.0"
    "aiohttp-3.12.14"
    "jinja2-3.1.6"
)

# Framework updates (merge after security)
FRAMEWORK_UPDATES=(
    "h11-0.16.0"
    "python-multipart-0.0.18"
    "langchain-core-0.1.53"
    "langchain-0.2.5"
    "langchain-community-0.2.19"
    "gradio-4.44.1"
)

# Function to merge a dependabot branch
merge_dependabot_update() {
    local branch_suffix=$1
    local branch_name="dependabot/pip/${branch_suffix}"
    
    echo "📦 Processing: ${branch_suffix}"
    
    # Check if branch exists
    if git branch -r | grep -q "origin/${branch_name}"; then
        echo "✅ Branch found: ${branch_name}"
        
        # Checkout and merge
        git checkout main
        git pull origin main
        git merge "origin/${branch_name}" --no-ff -m "Merge dependabot update: ${branch_suffix}"
        
        if [ $? -eq 0 ]; then
            echo "✅ Successfully merged: ${branch_suffix}"
            git push origin main
        else
            echo "❌ Merge conflict in: ${branch_suffix}"
            git merge --abort
            return 1
        fi
    else
        echo "⚠️  Branch not found: ${branch_name}"
    fi
    
    echo "---"
}

# Start with security updates
echo "🔥 Phase 1: Security Updates"
for update in "${SECURITY_UPDATES[@]}"; do
    merge_dependabot_update "$update"
done

echo ""
echo "📊 Phase 2: Framework Updates"
for update in "${FRAMEWORK_UPDATES[@]}"; do
    merge_dependabot_update "$update"
done

echo ""
echo "🎉 Dependabot update process complete!"
echo "📋 Check requirements.txt to verify all updates were applied correctly."

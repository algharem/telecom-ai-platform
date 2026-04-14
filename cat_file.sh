find . -type f \( -name "*.py" -o -name "*.yaml" \) \
  ! -path "src/components/*" \
  ! -path "src/hooks/*" \
  -print0 | while IFS= read -r -d '' file; do  
    echo "// $file" 
    echo "// ------------------------"  
    cat "$file"   
    echo "" 
done > combined_code.txt


# find src -type f \( -name "*.tsx" -o -name "*.ts" \) -print0 | while IFS= read -r -d '' file; do
#   echo "// $file"
#   echo "// ------------------------"
#   # cat "$file"
#   echo ""
# done 
# # > combined_code.ts

# app  components  hooks  lib

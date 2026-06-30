import json
import uuid

with open('international_schools_separated.json', 'r', encoding='utf-8') as f:
    schools = json.load(f)

# Generate ALL new IDs for every entry
for school in schools:
    new_id = uuid.uuid4().hex[:24]
    school['_id']['$oid'] = new_id

with open('international_schools_new.json', 'w', encoding='utf-8') as f:
    json.dump(schools, f, indent=2, ensure_ascii=False)

# Verify all IDs are unique
all_ids = [s['_id']['$oid'] for s in schools]
print(f'Total entries: {len(schools)}')
print(f'Unique IDs: {len(set(all_ids))}')
print(f'All unique: {len(all_ids) == len(set(all_ids))}')
print(f'Saved to international_schools_new.json')

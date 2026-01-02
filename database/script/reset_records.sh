#!/bin/bash
# Reset records and messages tables (keeps farmers)

psql -U postgres -d logbook -c "TRUNCATE records, messages CASCADE;"

echo "Records and messages have been deleted."

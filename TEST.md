# Testing the AI Logbook API

## API Documentation

Open the interactive docs at: http://localhost:8000/api/docs

## Health Check

```bash
curl http://localhost:8000/health
```

## Farmer Endpoints

### Create a farmer

```bash
curl -X POST http://localhost:8000/api/farmers \
  -H "Content-Type: application/json" \
  -d '{
    "external_id": "F001",
    "name": "U Kyaw",
    "phone_number": "+959123456789"
  }'
```

### List all farmers

```bash
curl http://localhost:8000/api/farmers
```

### Get farmer by ID

```bash
curl http://localhost:8000/api/farmers/{farmer_id}
```

### Get farmer by external ID

```bash
curl http://localhost:8000/api/farmers/external/F001
```

### Update a farmer

```bash
curl -X PUT http://localhost:8000/api/farmers/{farmer_id} \
  -H "Content-Type: application/json" \
  -d '{
    "name": "U Kyaw Win"
  }'
```

### Delete a farmer

```bash
curl -X DELETE http://localhost:8000/api/farmers/{farmer_id}
```

## Record Endpoints

### List all records

```bash
curl http://localhost:8000/api/records
```

### List records with filters

```bash
# Filter by farmer
curl "http://localhost:8000/api/records?farmer_id={farmer_id}"

# Filter by record type
curl "http://localhost:8000/api/records?record_type=chemical_spray"

# Filter by date range
curl "http://localhost:8000/api/records?date_from=2024-01-01&date_to=2024-12-31"

# Filter records needing followup
curl "http://localhost:8000/api/records?needs_followup=true"
```

### Get records needing followup

```bash
curl http://localhost:8000/api/records/followup
```

### Get record by ID

```bash
curl http://localhost:8000/api/records/{record_id}
```

## Extraction Endpoint (Manual Testing)

### Test text extraction

```bash
curl -X POST http://localhost:8000/api/extract \
  -H "Content-Type: application/json" \
  -d '{
    "farmer_id": "F001",
    "farmer_name": "U Kyaw",
    "input_mode": "text",
    "transcript": "Yesterday I sprayed pesticide on my tomato field row 3"
  }'
```

### Test with fertilizer application

```bash
curl -X POST http://localhost:8000/api/extract \
  -H "Content-Type: application/json" \
  -d '{
    "farmer_id": "F001",
    "farmer_name": "U Kyaw",
    "input_mode": "text",
    "transcript": "Today I applied urea fertilizer 50kg per acre on my rice paddy in plot 2"
  }'
```

### Test with multiple activities

```bash
curl -X POST http://localhost:8000/api/extract \
  -H "Content-Type: application/json" \
  -d '{
    "farmer_id": "F001",
    "farmer_name": "U Kyaw",
    "input_mode": "text",
    "transcript": "This morning I irrigated my tomato field and then sprayed fungicide in the afternoon"
  }'
```

### Test voice message simulation

```bash
curl -X POST http://localhost:8000/api/extract \
  -H "Content-Type: application/json" \
  -d '{
    "farmer_id": "F001",
    "farmer_name": "U Kyaw",
    "input_mode": "voice",
    "transcript": "uh yesterday I bought some chemicals from the shop in town, got two bottles of insecticide"
  }'
```

## WhatsApp Webhook

The webhook endpoint is at: `POST /api/webhook/whatsapp`

Configure this URL in your Twilio console:
```
https://your-domain.ngrok-free.app/api/webhook/whatsapp
```

### Simulate webhook (for testing)

```bash
curl -X POST http://localhost:8000/api/webhook/whatsapp \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "MessageSid=SM123456789" \
  -d "From=whatsapp:+959123456789" \
  -d "To=whatsapp:+14155238886" \
  -d "Body=Today I harvested 100 packs of tomatoes from plot 1 and sent to Yangon market" \
  -d "NumMedia=0" \
  -d "ProfileName=U Kyaw"
```

## Record Types

Available record types for filtering:
- `seed_purchase_and_sowing`
- `hazard_evaluation`
- `chemical_spray`
- `chemical_purchase`
- `chemical_disposal`
- `post_harvest_chemical_usage`
- `fertilizer_application`
- `irrigation`
- `spraying_tool_sanitation`
- `harvest_and_packaging`
- `training_update`
- `correction_report`
- `unknown`

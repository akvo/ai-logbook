#!/bin/bash

BASE_URL="http://localhost:8000"

echo "=== AI Logbook API Test ==="
echo ""

# Create a farmer
echo "1. Creating farmer..."
FARMER_RESPONSE=$(curl -s -X POST "$BASE_URL/api/farmers" \
  -H "Content-Type: application/json" \
  -d '{
    "external_id": "F002",
    "name": "Pak Budi Santoso",
    "phone_number": "+6281234567890"
  }')

echo "$FARMER_RESPONSE" | jq . 2>/dev/null || echo "$FARMER_RESPONSE"
echo ""

# Test extraction
echo "2. Testing extraction (chemical spray)..."
INPUT_TRANSCRIPT="Kemarin anak saya sudah semprot pestisida di kebun tomat baris 3 pakai sprayer gendong kira-kira habis setengah liter, sekarang sih tanamannya sehat, ini sudah minggu kedua, tapi daun-daunnya mulai ada bintik kuning kecil, mungkin karena serangan hama lagi ya, cuaca juga lagi sering hujan. Saya pakai pestisida jenis organik yang kemarin direkomendasikan sama penyuluh pertanian, soalnya saya pengen hasil panennya nanti aman untuk dikonsumsi keluarga saya juga."
echo "Input: $INPUT_TRANSCRIPT"
EXTRACT_RESPONSE=$(curl -s -X POST "$BASE_URL/api/extract" \
  -H "Content-Type: application/json" \
  -d '{
    "farmer_id": "F002",
    "farmer_name": "Pak Budi Santoso",
    "input_mode": "text",
    "transcript": "'"${INPUT_TRANSCRIPT}"'"
  }')

echo "$EXTRACT_RESPONSE" | jq . 2>/dev/null || echo "$EXTRACT_RESPONSE"
echo ""

# Test extraction with multiple activities
echo "3. Testing extraction (multiple activities)..."
INPUT_TRANSCRIPT="Pagi tadi saya kasih pupuk urea 50kg di sawah padi petak 2, terus sore saya siram sawahnya"
echo "Input: $INPUT_TRANSCRIPT"
EXTRACT_RESPONSE2=$(curl -s -X POST "$BASE_URL/api/extract" \
  -H "Content-Type: application/json" \
  -d '{
    "farmer_id": "F002",
    "farmer_name": "Pak Budi Santoso",
    "input_mode": "voice",
    "transcript": "'"${INPUT_TRANSCRIPT}"'"
  }')

echo "$EXTRACT_RESPONSE2" | jq . 2>/dev/null || echo "$EXTRACT_RESPONSE2"
echo ""

# Test extraction with harvest
echo "4. Testing extraction (harvest)..."
INPUT_TRANSCRIPT="Hari ini panen tomat 50 karung dari petak 1, dikirim ke pasar Kramat Jati Jakarta"
echo "Input: $INPUT_TRANSCRIPT"
EXTRACT_RESPONSE3=$(curl -s -X POST "$BASE_URL/api/extract" \
  -H "Content-Type: application/json" \
  -d '{
    "farmer_id": "F002",
    "farmer_name": "Pak Budi Santoso",
    "input_mode": "text",
    "transcript": "'"${INPUT_TRANSCRIPT}"'"
  }')

echo "$EXTRACT_RESPONSE3" | jq . 2>/dev/null || echo "$EXTRACT_RESPONSE3"
echo ""

# List farmers
echo "5. Listing farmers..."
curl -s "$BASE_URL/api/farmers" | jq .
echo ""

echo "=== Test Complete ==="

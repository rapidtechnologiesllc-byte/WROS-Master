#!/bin/bash

echo "=========================================="
echo "TESTING ZERO-PERMISSION LOGIN FIX"
echo "=========================================="
echo

# Test 1: Login with valid admin user (should work)
echo "TEST 1: Login with valid admin user"
echo "---"
curl -s -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@blitzenx.com","password":"Admin@123"}' \
  | jq '.' | head -20
echo

# Test 2: Check what happens with invalid credentials (should fail)
echo "TEST 2: Login with wrong password (should fail)"
echo "---"
curl -s -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@blitzenx.com","password":"WrongPassword"}' \
  | jq '.' 
echo

# Test 3: Try login with non-existent user
echo "TEST 3: Login with non-existent user (should fail)"
echo "---"
curl -s -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"nonexistent@blitzenx.com","password":"Password123"}' \
  | jq '.'
echo

echo "=========================================="
echo "TESTS COMPLETE"
echo "=========================================="

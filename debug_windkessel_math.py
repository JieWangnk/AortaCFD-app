"""
Debug Windkessel calculation to understand the math
"""
import math

# Given values from your p file
R_outlet1 = 388430416.39720386
C_outlet1 = 1.0297854728012991e-10
Z_outlet1 = 38843041.63972039

# Reference values from CoA_test
R_ref = 1000
C_ref = 1e-6
Z_ref = 100

print("=== CURRENT VALUES (from your simulation) ===")
print(f"R = {R_outlet1:.2e} Pa·s/m³")
print(f"C = {C_outlet1:.2e} m³/Pa")
print(f"Z = {Z_outlet1:.2e} Pa·s/m³")
print(f"Ratio R/Z = {R_outlet1/Z_outlet1:.1f}")
print(f"RC time constant = {R_outlet1 * C_outlet1:.6f} s")

print("\n=== REFERENCE VALUES (CoA_test) ===")
print(f"R = {R_ref:.2e} Pa·s/m³")
print(f"C = {C_ref:.2e} m³/Pa")
print(f"Z = {Z_ref:.2e} Pa·s/m³")
print(f"Ratio R/Z = {R_ref/Z_ref:.1f}")
print(f"RC time constant = {R_ref * C_ref:.6f} s")

print("\n=== SCALING FACTOR ===")
print(f"Your R is {R_outlet1/R_ref:.0f}x too large")
print(f"Your C is {C_outlet1/C_ref:.0f}x too small")
print(f"Your Z is {Z_outlet1/Z_ref:.0f}x too large")

print("\n=== REVERSE ENGINEERING: What radius gives R=1000? ===")
mu = 0.004  # Pa·s
r_multiplier = 10.0
vessel_length_factor = 4.0

# From code: R_min = r_multiplier * max(K*L)
# K*L = 8*mu*L / (pi*r^4)
# R_min = r_multiplier * 8*mu*L / (pi*r^4)
# R_min = r_multiplier * 8*mu*(4*r) / (pi*r^4)
# R_min = r_multiplier * 32*mu / (pi*r^3)

# Solve for r:
# r^3 = r_multiplier * 32*mu / (pi*R_min)

R_target = 1000
r_cubed = r_multiplier * 32 * mu / (math.pi * R_target)
r_meters = r_cubed ** (1/3)
r_mm = r_meters * 1000

print(f"Radius needed for R={R_target}: {r_mm:.1f} mm")

print("\n=== ACTUAL CALCULATION FROM YOUR DATA ===")
# Reverse calculate what radius was used
r3_actual = r_multiplier * 32 * mu / (math.pi * R_outlet1)
r_actual_m = r3_actual ** (1/3)
r_actual_mm = r_actual_m * 1000

print(f"Estimated outlet1 radius: {r_actual_mm:.2f} mm")
print(f"Estimated outlet1 diameter: {2*r_actual_mm:.2f} mm")

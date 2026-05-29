//
// Created by ATINOMI on 2026/5/29.
//
#include "main.h"
#include <math.h>

float angle_acc_compute(int16_t ax, int16_t ay, int16_t az)
{
    float angle_acc = atan2((float)ax, (float)az) / 3.14159f * 180.0f;
    return angle_acc;
}

float angle_gyro_compute(float angle_gyro, int16_t gy, float delta_t, float angle)
{
    angle_gyro = angle + gy / 32768.0 * 2000 * delta_t;
    return angle_gyro;
}

float complementary_filter(float angle_acc, float angle_gyro, float alpha)
{
    float angle = alpha * angle_gyro + (1 - alpha) * angle_acc;
    return angle;
}
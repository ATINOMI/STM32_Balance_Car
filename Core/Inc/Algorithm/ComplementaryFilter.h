//
// Created by ATINOMI on 2026/5/29.
//

#ifndef BALANCECAR_COMPLEMENTARYFILTER_H
#define BALANCECAR_COMPLEMENTARYFILTER_H

float angle_acc_compute(int16_t ax,int16_t ay,int16_t az);
float angle_gyro_compute(float angle_gyro, int16_t gy, float delta_t, float angle);
float complementary_filter(float angle_acc, float angle_gyro, float alpha);

#endif //BALANCECAR_COMPLEMENTARYFILTER_H

//
// Created by ATINOMI on 2026/5/29.
//

#ifndef BALANCECAR_MPU6050_H
#define BALANCECAR_MPU6050_H

void MPU6050_writeReg(uint8_t reg_addr, uint8_t data);

uint8_t MPU6050_readReg(uint8_t reg_addr);

void MPU6050_readRegs(uint8_t reg_addr, uint8_t *data_array, uint8_t len);

void MPU6050_init(void);

uint8_t MPU6050_get_id(void);

void MPU6050_getdata(int16_t *accx,
                     int16_t *accy,
                     int16_t *accz,
                     int16_t *gyrox,
                     int16_t *gyroy,
                     int16_t *gyroz) ;


#endif //BALANCECAR_MPU6050_H

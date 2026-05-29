//
// Created by ATINOMI on 2026/5/29.
//
#include  "main.h"
#include "HardWare/MPU6050_Reg.h"

#define MPU6050_ADDRESS 0xD0

extern I2C_HandleTypeDef hi2c2;

volatile uint8_t i2c_dma_done = 0;

void HAL_I2C_MemRxCpltCallback(I2C_HandleTypeDef *hi2c)
{
    if (hi2c->Instance == I2C2)
    {
        i2c_dma_done = 1;
    }
}

void MPU6050_writeReg(uint8_t reg_addr, uint8_t data)
{
    HAL_I2C_Mem_Write(&hi2c2, MPU6050_ADDRESS, reg_addr,
                      I2C_MEMADD_SIZE_8BIT, &data, 1, HAL_MAX_DELAY);
}

uint8_t MPU6050_readReg(uint8_t reg_addr)
{
    uint8_t data;
    HAL_I2C_Mem_Read(&hi2c2, MPU6050_ADDRESS, reg_addr,
                     I2C_MEMADD_SIZE_8BIT, &data, 1, HAL_MAX_DELAY);
    return data;
}

void MPU6050_readRegs(uint8_t reg_addr, uint8_t *data_array, uint8_t len)
{
    HAL_I2C_Mem_Read(&hi2c2, MPU6050_ADDRESS, reg_addr,
                     I2C_MEMADD_SIZE_8BIT, data_array, len, HAL_MAX_DELAY);
}
void MPU6050_init(void)
{
    MPU6050_writeReg(MPU6050_PWR_MGMT_1,   0x01);
    MPU6050_writeReg(MPU6050_PWR_MGMT_2,   0x00);
    MPU6050_writeReg(MPU6050_SMPLRT_DIV,   0x07);
    MPU6050_writeReg(MPU6050_CONFIG,       0x00);
    MPU6050_writeReg(MPU6050_GYRO_CONFIG,  0x18);
    MPU6050_writeReg(MPU6050_ACCEL_CONFIG, 0x18);
}

uint8_t MPU6050_get_id(void)
{
    return MPU6050_readReg(MPU6050_WHO_AM_I);
}

void MPU6050_getdata(int16_t *accx,
                     int16_t *accy,
                     int16_t *accz,
                     int16_t *gyrox,
                     int16_t *gyroy,
                     int16_t *gyroz)
{
    uint8_t data[14];

    MPU6050_readRegs(MPU6050_ACCEL_XOUT_H, data, 14);

    *accx = (data[0] << 8) | data[1];
    *accy = (data[2] << 8) | data[3];
    *accz = (data[4] << 8) | data[5];

    *gyrox = (data[8] << 8) | data[9];
    *gyroy = (data[10] << 8) | data[11];
    *gyroz = (data[12] << 8) | data[13];
}
//
// Created by ATINOMI on 2026/5/29.
//
#include "main.h"

void i2c_write_scl(uint8_t bit_value)
{
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_10, bit_value ? GPIO_PIN_SET : GPIO_PIN_RESET);
}

void i2c_write_sda(uint8_t bit_value)
{
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_11, bit_value ? GPIO_PIN_SET : GPIO_PIN_RESET);
}

uint8_t i2c_read_sda(void)
{
    uint8_t bit_value;
    bit_value = HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_11);
    return bit_value;
}

void i2c_start(void)
{
    i2c_write_sda(1);
    i2c_write_scl(1);
    i2c_write_sda(0);
    i2c_write_scl(0);
}

void i2c_stop(void)
{
    i2c_write_sda(0);
    i2c_write_scl(1);
    i2c_write_sda(1);
}

void i2c_send_byte(uint8_t byte)
{
    uint8_t i;
    for (i = 0; i < 8; i++)
    {
        i2c_write_sda(!!(byte & (0x80 >> i)));
        i2c_write_scl(1);
        i2c_write_scl(0);
    }
}

uint8_t i2c_read_byte(void)
{
    uint8_t i, byte = 0x00;
    i2c_write_sda(1);
    for (i = 0; i < 8; i++)
    {
        i2c_write_scl(1);
        if (i2c_read_sda()) byte |= (0x80 >> i);
        i2c_write_scl(0);
    }
    return byte;
}

void i2c_send_ack(uint8_t ack_bit)
{
    i2c_write_sda(ack_bit);
    i2c_write_scl(1);
    i2c_write_scl(0);
}

uint8_t i2c_read_ack(void)
{
    uint8_t ack_bit;
    i2c_write_sda(1);
    i2c_write_scl(1);
    ack_bit = i2c_read_sda();
    i2c_write_scl(0);
    return ack_bit;
}
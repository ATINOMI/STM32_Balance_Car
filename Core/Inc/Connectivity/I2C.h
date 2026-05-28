//
// Created by ATINOMI on 2026/5/29.
//

#ifndef BALANCECAR_I2C_H
#define BALANCECAR_I2C_H

void i2c_write_scl(uint8_t bit_value);
void i2c_write_sda(uint8_t bit_value);
uint8_t i2c_read_sda(void);
void i2c_start(void);
void i2c_send_byte(uint8_t byte);
uint8_t i2c_read_byte(void);
void i2c_send_ack(uint8_t ack_bit);
uint8_t i2c_read_ack(void);
void i2c_stop(void);

#endif //BALANCECAR_I2C_H

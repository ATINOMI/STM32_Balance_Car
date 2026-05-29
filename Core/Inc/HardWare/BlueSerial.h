//
// Created by ATINOMI on 2026/5/29.
//

#ifndef BALANCECAR_BLUESERIAL_H
#define BALANCECAR_BLUESERIAL_H

void blue_serial_send_byte(uint8_t byte);

void blue_serial_send_arry(uint8_t *arr, uint16_t len);

void blue_serial_send_str(char *str);

uint32_t blue_serial_pow(uint32_t x, uint32_t y);

void blue_serial_send_num(uint32_t num, uint8_t len);

void blue_serial_printf(char *fmt, ...);

#endif //BALANCECAR_BLUESERIAL_H

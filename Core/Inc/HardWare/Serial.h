//
// Created by ATINOMI on 2026/5/29.
//

#ifndef BALANCECAR_SERIAL_H
#define BALANCECAR_SERIAL_H
#include <stdio.h>
void serial_send_byte(uint8_t byte);

void serial_send_arry(uint8_t *arr, uint16_t len);

void serial_send_str(char *str);

uint32_t serial_pow(uint32_t x, uint32_t y);

void serial_send_num(uint32_t num, uint8_t len);

int fputc(int ch, FILE *f);

void serial_printf(char *fmt, ...);

uint8_t serial_get_rx_flag(void);

uint8_t serial_get_rx_data(void);

#endif //BALANCECAR_SERIAL_H

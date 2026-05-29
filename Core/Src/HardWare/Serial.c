//
// Created by ATINOMI on 2026/5/29.
//


#include <stdio.h>
#include <stdarg.h>
#include "main.h"

extern UART_HandleTypeDef huart1;
uint8_t serial_rx_data;
uint8_t serial_rx_flag;

void serial_send_byte(uint8_t byte)
{
    HAL_UART_Transmit(&huart1, (uint8_t*) &byte, 1, 10);
}

void serial_send_arry(uint8_t *arr, uint16_t len)
{
    uint16_t i;
    for (i = 0; i < len; i++)
    {
        serial_send_byte(arr[i]);
    }
}

void serial_send_str(char *str)
{
    uint8_t i;
    for (i = 0; str[i] != '\0'; i++)
    {
        serial_send_byte(str[i]);
    }
}

uint32_t serial_pow(uint32_t x, uint32_t y)
{
    uint32_t result = 1;
    while (y --)
    {
        result *= x;
    }
    return result;
}

void serial_send_num(uint32_t num, uint8_t len)
{
    uint8_t i;
    for (i = 0; i < len; i++)
    {
        serial_send_byte(num / serial_pow(10, len - i - 1) % 10 + '0');
    }
}

int fputc(int ch, FILE *f)
{
    serial_send_byte(ch);
    return ch;
}

void serial_printf(char *fmt, ...)
{
    char str[100];
    va_list arg;
    va_start(arg, fmt);
    vsprintf(str, fmt, arg);
    va_end(arg);
    serial_send_str(str);
}

uint8_t serial_get_rx_flag(void)
{
    if (serial_rx_flag == 1)
    {
        serial_rx_flag = 0;
        return 1;
    }
    return 0;
}

uint8_t serial_get_rx_data(void)
{
    return serial_rx_data;
}




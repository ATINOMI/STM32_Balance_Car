//
// Created by ATINOMI on 2026/5/29.
//

#include "main.h"
#include <stdarg.h>
#include <stdio.h>

extern UART_HandleTypeDef huart2;
char BlueSerial_RxPacket[100];
uint8_t BlueSerial_RxFlag;
uint8_t blue_rx_byte;

void blue_serial_send_byte(uint8_t byte)
{
    HAL_UART_Transmit(&huart2, (uint8_t*) &byte, 1, 10);
}

void blue_serial_send_arry(uint8_t *arr, uint16_t len)
{
    uint16_t i;
    for (i = 0; i < len; i++)
    {
        blue_serial_send_byte(arr[i]);
    }
}

void blue_serial_send_str(char *str)
{
    uint8_t i;
    for (i = 0; str[i] != '\0'; i++)
    {
        blue_serial_send_byte(str[i]);
    }
}

uint32_t blue_serial_pow(uint32_t x, uint32_t y)
{
    uint32_t result = 1;
    while (y --)
    {
        result *= x;
    }
    return result;
}

void blue_serial_send_num(uint32_t num, uint8_t len)
{
    uint8_t i;
    for (i = 0; i < len; i++)
    {
        blue_serial_send_byte(num / blue_serial_pow(10, len - i - 1) % 10 + '0');
    }
}

void blue_serial_printf(char *fmt, ...)
{
    char str[100];
    va_list arg;
    va_start(arg, fmt);
    vsprintf(str, fmt, arg);
    va_end(arg);
    blue_serial_send_str(str);
}
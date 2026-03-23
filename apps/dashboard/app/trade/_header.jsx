'use client';
import React, { useState, useEffect, useRef } from 'react';
import { getTrades, getWallet, getFullWallet, getPositionValue, sellTrade, getAchievements } from '@/lib/api';
import { useAchievement } from '@/components/AchievementContext';
import { useTelegram } from '@/hooks/useTelegram';
import { useTradingMode } from '@/components/TradingModeContext';
import AuthGate from '@/components/AuthGate';
import Navbar from '@/components/Navbar';

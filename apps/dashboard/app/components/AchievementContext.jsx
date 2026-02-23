'use client';
import React, { createContext, useContext, useState, useCallback } from 'react';

const AchievementContext = createContext(null);

export function AchievementProvider({ children }) {
  const [notification, setNotification] = useState(null);

  const showAchievement = useCallback((achievement) => {
    setNotification(achievement);
    setTimeout(() => setNotification(null), 3500);
  }, []);

  return (
    <AchievementContext.Provider value={{ showAchievement, notification }}>
      {children}
      {notification && (
        <div className="ach-popup">
          <div className="apu-icon">{notification.icon}</div>
          <div className="apu-t">
            <div className="apt">ACHIEVEMENT UNLOCKED</div>
            <div className="apn">{notification.name}</div>
            <div className="apx">+{notification.xp} XP</div>
          </div>
        </div>
      )}
    </AchievementContext.Provider>
  );
}

export function useAchievement() {
  const context = useContext(AchievementContext);
  if (!context) {
    return { showAchievement: () => {}, notification: null };
  }
  return context;
}

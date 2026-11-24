import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { Farm, Field } from '../types';
import { getFarms } from '../services/farmService';

interface FieldContextValue {
  farms: Farm[];
  selectedFarmId: number;
  selectedFieldId: number;
  selectedField: Field | null;
  setSelectedFarmId: (id: number) => void;
  setSelectedFieldId: (id: number) => void;
  refreshFarms: (selectFieldId?: number) => Promise<void>;
  loadingFarms: boolean;
}

const FieldContext = createContext<FieldContextValue>({
  farms: [],
  selectedFarmId: 1,
  selectedFieldId: 1,
  selectedField: null,
  setSelectedFarmId: () => {},
  setSelectedFieldId: () => {},
  refreshFarms: async () => {},
  loadingFarms: true,
});

export const FieldProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [farms, setFarms] = useState<Farm[]>([]);
  const [selectedFarmId, setSelectedFarmId] = useState<number>(1);
  const [selectedFieldId, setSelectedFieldId] = useState<number>(1);
  const [loadingFarms, setLoadingFarms] = useState<boolean>(true);

  const refreshFarms = useCallback(async (selectFieldId?: number) => {
    try {
      const res = await getFarms();
      const loadedFarms = res.data || [];
      setFarms(loadedFarms);

      if (selectFieldId) {
        for (const f of loadedFarms) {
          if (f.fields?.some((fld) => fld.id === selectFieldId)) {
            setSelectedFarmId(f.id);
            setSelectedFieldId(selectFieldId);
            return;
          }
        }
      }

      if (loadedFarms.length > 0) {
        const currentFarm = loadedFarms.find((f) => f.id === selectedFarmId) || loadedFarms[0];
        setSelectedFarmId(currentFarm.id);
        const fields = currentFarm.fields || [];
        if (fields.length > 0 && !fields.some((fld) => fld.id === selectedFieldId)) {
          setSelectedFieldId(fields[0].id);
        }
      }
    } catch (err) {
      console.error('Failed to load farms:', err);
    } finally {
      setLoadingFarms(false);
    }
  }, [selectedFarmId, selectedFieldId]);

  useEffect(() => {
    refreshFarms();
  }, []);

  const currentFarm = farms.find((f) => f.id === selectedFarmId) || farms[0];
  const selectedField =
    currentFarm?.fields?.find((fld) => fld.id === selectedFieldId) ||
    currentFarm?.fields?.[0] ||
    null;

  const handleSelectFarm = (farmId: number) => {
    setSelectedFarmId(farmId);
    const farm = farms.find((f) => f.id === farmId);
    if (farm?.fields && farm.fields.length > 0) {
      setSelectedFieldId(farm.fields[0].id);
    }
  };

  return (
    <FieldContext.Provider
      value={{
        farms,
        selectedFarmId,
        selectedFieldId: selectedField?.id ?? selectedFieldId,
        selectedField,
        setSelectedFarmId: handleSelectFarm,
        setSelectedFieldId,
        refreshFarms,
        loadingFarms,
      }}
    >
      {children}
    </FieldContext.Provider>
  );
};

export const useFieldContext = () => useContext(FieldContext);
